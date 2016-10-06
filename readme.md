# What's this ?
This is an HTTP log parser. It reads log lines in Common Log Format (CLF)
and prints some useful statistics (top Hits, bandwidth)
on stdout at regular intervals. It also print alerts on the console whenever
certain thresholds are crossed.

## Requirements
* Python 2.7
* Tox

## Run
To launch the program in a virtualenv, just do
```console
tail -f /var/log/apache2/access.log | monitor_http_log
OR
monitor_http_log /var/log/apache2/access.log
```

## Test
To run the unit tests in a virtualenv, just do
```console
tox -e py27
```

## Lint
To run the code linter, just do
```console
tox -e pep8
```
