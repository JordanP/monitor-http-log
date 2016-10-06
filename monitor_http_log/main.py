import argparse
import collections
import datetime
import logging
import logging.handlers
import os
import re
import select
import sys
import time
import urlparse

import monitor_http_log.heapq_oo as heapq_oo

from monitor_http_log import exceptions

# Keep all data points for the last `HISTORY` seconds
HISTORY = 10
# Store all data points in a heap
LAST_HITS = heapq_oo.HeapQ()
# Also aggregate the data to avoid traversing `LAST_HITS`
# This is a CPU/memory tradeoff
LAST_HITS_PER_SECTION = collections.Counter()
BYTES_PER_SECONDS = collections.defaultdict(int)

# Print statistics every `STATS_INTERVAL` seconds
STATS_INTERVAL = 10

# An alarm will be triggered if the bandwidth usage has been more than
# `ALARM_BW_TRESHOLD` bytes on average in the last `ALARM_BW_PERIOD` seconds
ALARM_BW_TRESHOLD = 1000
ALARM_BW_PERIOD = 20

# Overall traffic in the last `HISTORY` seconds
LAST_BW = 0

# Some constants
ALARM_STATE_HIGH = object()
ALARM_STATE_LOW = object()

COMMON_LOG_FORMAT = re.compile(
    r'(?P<client_ip>[^ ]*) (?P<user_identifier>[^ ]*) (?P<user_id>[^ ]*)'
    r' \[(?P<date>[^]]*)\] "(?P<http_method>[A-Z]*) (?P<http_url>[^"]*) '
    r'(?P<http_version>HTTP/\d.\d)" (?P<status_code>[^ ]*) '
    r'(?P<bytes_sent>[^ ]*)'
)


def parse_log_line(line):
    matches = COMMON_LOG_FORMAT.match(line)

    if matches is None:
        # For instance an HTTP 408 (Request Timeout) could have no HTTP url
        logging.warning("Unable to parse HTTP log line : '%s'", line)
        raise exceptions.InvalidHTTPLogLine()

    hit = matches.groupdict()

    # Build section
    parse_result = urlparse.urlparse(hit['http_url'])
    path_section = "/".join(parse_result.path.split('/')[:2])
    # According to instructions, a section also contains the scheme and netloc
    hit['section'] = urlparse.urlunparse(
        (parse_result.scheme, parse_result.netloc, path_section, '', '', '')
    )

    # Convert date to unix timestamp (we assume the log stream comes from the
    # same server as where this program is running, to avoid dealing with TZ,
    # "the %z escape that expands to the preferred hour/minute offset is not
    # supported by all ANSI C libraries")
    hit["time"] = time.mktime(
        time.strptime(hit["date"].split()[0], "%d/%b/%Y:%H:%M:%S")
    )

    try:
        hit['bytes_sent'] = int(hit['bytes_sent'])
    except ValueError:
        # An HTTP DELETE returns no data so bytes_sent is '-'
        hit['bytes_sent'] = 0

    return hit


def update_statistics():
    global LAST_BW

    # Discard hits that are old from the statistics
    horizon = time.time() - HISTORY
    for _, hit in LAST_HITS.popuntil((horizon,)):
        LAST_HITS_PER_SECTION[hit['section']] -= 1
        LAST_BW -= hit['bytes_sent']


def print_statistics():
    total_bandwidth_in_kb = LAST_BW / 1024

    print("In the last {} seconds").format(HISTORY)
    print("Top sections : %r" % LAST_HITS_PER_SECTION.most_common(3))
    print("Total Hits / Total bandwidth: {} / {} KiB".format(
        len(LAST_HITS), total_bandwidth_in_kb))
    print("-" * 80)


def update_and_print_stats():
    # First discard old data in order to have accurate stats.
    update_statistics()
    print_statistics()

    last_printed = time.time()
    return last_printed


def evaluate_alarm(data, alarm_state, alarm_treshold, alarm_period):
    new_alarm_state = alarm_state
    aggregated_bandwidth = 0

    # Data points older than `horizon` are not going to be looked at.
    horizon = time.time() - alarm_period
    for timestamp in data.keys():
        if timestamp < horizon:
            del data[timestamp]
        else:
            aggregated_bandwidth += data[timestamp]

    avg = aggregated_bandwidth / alarm_period
    if avg >= alarm_treshold and alarm_state == ALARM_STATE_LOW:
        new_alarm_state = ALARM_STATE_HIGH
        print("\033[93mHigh traffic generated an alert - traffic = {} B/s, "
              "triggered at {}\033[0m").format(avg, datetime.datetime.now())
    elif avg < alarm_treshold and alarm_state == ALARM_STATE_HIGH:
        new_alarm_state = ALARM_STATE_LOW
        print("\033[92mAlert recovered at {}\033[0m".format(
            datetime.datetime.now()))

    return new_alarm_state


def process_hit(hit):
    global LAST_BW
    logging.debug("Got hit: %s", hit)
    LAST_HITS_PER_SECTION[hit['section']] += 1
    LAST_HITS.add((hit['time'], hit))
    LAST_BW += hit['bytes_sent']
    BYTES_PER_SECONDS[hit['time']] += hit['bytes_sent']


def process_logs_forever(http_logs):
    stats_last_printed = time.time()
    alarm_state = ALARM_STATE_LOW

    while True:
        # We set a timeout to select because we don't want the program to
        # freeze if no HTTP hit.
        readable = select.select([http_logs], [], [], 0.5)[0]
        if not readable:
            # Nothing to read.
            if time.time() - stats_last_printed >= STATS_INTERVAL:
                stats_last_printed = update_and_print_stats()
            alarm_state = evaluate_alarm(
                BYTES_PER_SECONDS, alarm_state,
                ALARM_BW_TRESHOLD, ALARM_BW_PERIOD
            )
        else:
            log_line = readable[0].readline().strip()
            # If we are at the end of the file (EOF) then `readline()` is
            # going to return ''.
            if not log_line:
                if time.time() - stats_last_printed >= STATS_INTERVAL:
                    stats_last_printed = update_and_print_stats()
                alarm_state = evaluate_alarm(
                    BYTES_PER_SECONDS, alarm_state,
                    ALARM_BW_TRESHOLD, ALARM_BW_PERIOD
                )
                # We don't want readline() to keep returning EOF
                # so wait for new HTTP hits to come.
                time.sleep(0.5)
            else:
                try:
                    hit = parse_log_line(log_line)
                except exceptions.InvalidHTTPLogLine:
                    continue
                process_hit(hit)


def main():
    parser = argparse.ArgumentParser(
        description='HTTP log monitoring console program',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-v', '--verbose', help='Log at DEBUG level',
        dest='verbose', action='store_true'
    )
    parser.add_argument(
        '-q', '--quiet', help='Log at WARNING level',
        dest='quiet', action='store_true'
    )

    parser.add_argument(
        '-f', '--file', help='Path to the HTTP log file',
        dest='httplog_file',
    )

    args = parser.parse_args()

    logger = logging.getLogger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.INFO)

    if args.httplog_file:
        http_logs = open(args.httplog_file, 'rt')
        http_logs.seek(0, os.SEEK_END)
    else:
        # We can also invoke this program with
        # tail -f /var/log/apache2/other_vhosts_access.log | monitor_http_log
        http_logs = sys.stdin

    process_logs_forever(http_logs)


if __name__ == '__main__':
    sys.exit(main())
