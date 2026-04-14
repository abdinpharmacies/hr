import datetime


def last_day_of_month(any_date):
    # this will never fail
    # get close to the end of the month for any day, and add 4 days 'over'
    next_month = any_date.replace(day=28) + datetime.timedelta(days=4)
    # subtract the number of remaining 'overage' days to get last day of current month
    # , or said programmaticaly said, the previous day of the first of next month
    return next_month - datetime.timedelta(days=next_month.day)
