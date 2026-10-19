/** @odoo-module **/

const roundMoney = (value) => Number(value.toFixed(3));

/** Reverse the purchase line's tax and discount formula into a unit price. */
export function reverseLineCost({ total, qty, bonus = 0, discounts = [], taxes = [] }) {
    if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(qty) || qty <= 0
        || !Number.isInteger(bonus) || bonus < 0
        || discounts.some((rate) => !Number.isFinite(rate) || rate < 0 || rate >= 100)
        || taxes.some((tax) => !Number.isFinite(Number(tax.percentage)) || Number(tax.percentage) < 0)) {
        throw new RangeError("Invalid reverse cost inputs");
    }
    const discountFactor = discounts.reduce((factor, rate) => factor * (1 - rate / 100), 1);
    const effectiveDiscount = roundMoney((1 - discountFactor) * 100);
    const appliedFactor = 1 - effectiveDiscount / 100;
    if (appliedFactor <= 0) {
        throw new RangeError("The combined discount is too large");
    }
    const baseTax = taxes.filter((tax) => !tax.apply_on_total)
        .reduce((rate, tax) => rate + Number(tax.percentage) / 100, 0);
    const totalTax = taxes.filter((tax) => tax.apply_on_total)
        .reduce((rate, tax) => rate + Number(tax.percentage) / 100, 0);
    const taxRate = baseTax + totalTax * (1 + baseTax);
    const coefficient = appliedFactor * (qty + (qty + bonus) * taxRate);
    if (!Number.isFinite(coefficient) || coefficient <= 0) {
        throw new RangeError("The purchase line cannot be reversed");
    }
    const purchasePrice = roundMoney(total / coefficient);
    if (!Number.isFinite(purchasePrice) || purchasePrice <= 0) {
        throw new RangeError("The unit price rounds to zero");
    }
    const netUnitPrice = purchasePrice * appliedFactor;
    const calculatedTotal = roundMoney(netUnitPrice * (qty + (qty + bonus) * taxRate));
    return {
        purchasePrice,
        effectiveDiscount,
        unitCost: roundMoney(netUnitPrice * (1 + taxRate)),
        calculatedTotal,
        difference: roundMoney(calculatedTotal - total),
    };
}

/** Calculate the unit sale price from the paid quantity's sale total. */
export function unitSalePriceFromTotal(total, qty) {
    if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(qty) || qty <= 0) {
        throw new RangeError("Invalid sale price inputs");
    }
    const salePrice = roundMoney(total / qty);
    if (salePrice <= 0) {
        throw new RangeError("The unit sale price rounds to zero");
    }
    const calculatedTotal = roundMoney(salePrice * qty);
    return { salePrice, calculatedTotal, difference: roundMoney(calculatedTotal - total) };
}
