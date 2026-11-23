# Held-out persistence score, counted by hand

Household `HH-HELD-01`, local day 2026-06-15, America/Los_Angeles, 5-minute buckets. Volumes below are liters in that bucket. The 11:30 bucket is absent. The midnight bucket is duplicated in the file and counts once.

Training household `HH-TRAIN-01` is a different household and a different day. Its planted leak runs 15:00–15:20 at 0.4 L. Its shower and appliance cycle each last 10 minutes. The grid is flow in {0.25, 0.5, 1, 5} liters and persistence in {5, 10, 15, 20} minutes. Recall is maximized, then false alarms are minimized, then the higher flow and the longer persistence win.

- 0.50 L and above misses the 0.4 L training leak.
- 5 minutes of persistence also flags the 10-minute shower (the second bucket starts 5 minutes after the run starts).
- 10 and 15 minutes catch the training leak and do not flag the shower or the appliance.
- 20 minutes never reaches a bucket inside the 20-minute training leak.
- The conservative winner is 0.25 L and 15 minutes.

Held-out planted events:

1. `E-HELD-LEAK-P`, 10:00–11:00 at 0.4 L every bucket. The 15-minute rule opens at 10:15 and closes at 11:00. Delay = 15 minutes. This is the one true positive.
2. `E-HELD-LEAK-I`, 13:00–13:35, with water only at 13:00, 13:15, and 13:30. Each pulse is its own run because the buckets between them are observed zeros. No run lasts 15 minutes. This is the one false negative.

Normal use that the same rule flags:

- `E-HELD-IRR`, 08:00–08:40 at 1.2 L. The alarm opens at 08:15 and closes at 08:40. It does not overlap a planted leak, so it is the one false positive.
- The 07:00 shower lasts 10 minutes and does not open a 15-minute alarm.

Confusion totals: true positive 1, false positive 1, false negative 1. Precision = 1/2 = 0.5. Recall = 1/2 = 0.5. Median delay of the one detection = 15 minutes.

Eligible days: 288 − 1 = 287 observed slots. 287/288 ≥ 0.90, so the day stays in the denominator. False alerts per eligible household-day = 1/1 = 1.

Two alarms are not given credit for `E-HELD-LEAK-P`. The irrigation alarm does not overlap it, and there is no second leak alarm.
