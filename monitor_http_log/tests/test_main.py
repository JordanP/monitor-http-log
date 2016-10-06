import time
import unittest

from monitor_http_log.main import ALARM_STATE_HIGH
from monitor_http_log.main import ALARM_STATE_LOW
from monitor_http_log.main import evaluate_alarm


class TestMain(unittest.TestCase):

    def setUp(self):
        self.now = time.time()

    def test_evaluate_alarm_with_no_data(self):
        # No data => everything is calm => alarm should be stopped
        new_state = evaluate_alarm(
            {}, ALARM_STATE_HIGH, alarm_treshold=1, alarm_period=1)
        self.assertEqual(ALARM_STATE_LOW, new_state)

        # No data => everything is calm => alarm should kept stopped
        new_state = evaluate_alarm(
            {}, ALARM_STATE_LOW, alarm_treshold=1, alarm_period=1)
        self.assertEqual(ALARM_STATE_LOW, new_state)

    def test_evaluate_alarm_with_treshold_just_hit(self):
        threshold = 4242
        data = {self.now: threshold}

        new_state_when_alarm_was_down = evaluate_alarm(
            data, ALARM_STATE_LOW, alarm_treshold=threshold, alarm_period=1)
        self.assertEqual(ALARM_STATE_HIGH, new_state_when_alarm_was_down)

        new_state_when_alarm_was_high = evaluate_alarm(
            data, ALARM_STATE_HIGH, alarm_treshold=threshold, alarm_period=1)
        self.assertEqual(ALARM_STATE_HIGH, new_state_when_alarm_was_high)

    def test_evaluate_alarm_front_up(self):
        history = 42
        data = {
            # That data point should be discarded because it's old
            self.now - history - 1: -1000,
            self.now: history
        }

        new_state = evaluate_alarm(
            data, ALARM_STATE_LOW, alarm_treshold=1, alarm_period=history)
        # We have data/history >= threshold so alert
        self.assertEqual(ALARM_STATE_HIGH, new_state)
        self.assertNotIn(self.now - history - 1, data)

    def test_evaluate_alarm_test_average(self):
        data = {
            self.now - 2: 4,
            self.now - 1: 5,
            self.now: 6
        }
        # If my maths are good, average over the last 3 seconds is 5.
        state = evaluate_alarm(
            data, ALARM_STATE_LOW, alarm_treshold=4.9, alarm_period=3)
        self.assertEqual(ALARM_STATE_HIGH, state)

        state = evaluate_alarm(
            data, ALARM_STATE_HIGH, alarm_treshold=5.1, alarm_period=3)
        self.assertEqual(ALARM_STATE_LOW, state)
