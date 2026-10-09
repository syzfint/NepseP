import pandas as pd
from pandas.tseries.holiday import AbstractHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

class NepseHolidayCalendar(AbstractHolidayCalendar):
    rules = []

NEPSE_BUS_DAY = CustomBusinessDay(weekmask="Sun Mon Tue Wed Thu", calendar=NepseHolidayCalendar())

test_dates = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06"]
for d in test_dates:
    dt = pd.to_datetime(d)
    res = dt + NEPSE_BUS_DAY
    print(f"{d} ({dt.strftime('%A')}) + 1 NEPSE_BUS_DAY = {res.strftime('%Y-%m-%d (%A)')}")
