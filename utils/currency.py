FX_FROM_SGD = {
    "SGD": 1.0,
    "USD": 1 / 1.32,
    "VND": 19_500 / 1.32,
    "GBP": 1 / 1.72,
}

CURRENCIES = list(FX_FROM_SGD.keys())


def convert(sgd_amount, to_currency):
    if to_currency == "SGD":
        return sgd_amount
    return sgd_amount * FX_FROM_SGD[to_currency]


def fmt(sgd_amount, currency, decimals=0):
    converted = convert(sgd_amount, currency)
    if decimals == 0:
        return f"{currency} {converted:,.0f}"
    return f"{currency} {converted:,.{decimals}f}"
