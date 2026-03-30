# دالة تساعد على ربط أجزاء الرقم باستخدام "و" بدون فواصل إضافية
def join_with_waw(parts):
    if not parts:
        return ""
    result = parts[0]
    for p in parts[1:]:
        result += " و" + p
    return result


# قوائم الأرقام
ones_list = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
teens_list = ["عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر", "أربعة عشر", "خمسة عشر", "ستة عشر", "سبعة عشر", "ثمانية عشر",
              "تسعة عشر"]
tens_list = ["", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
hundreds_list = ["", "مائة", "مائتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]


# دالة تحويل رقم من 0 إلى 999 إلى نص عربي
def convert_hundreds(n):
    parts = []
    h = n // 100  # عدد المئات
    remainder = n % 100  # العدد المتبقي (العشرات والآحاد)

    if h > 0:
        parts.append(hundreds_list[h])

    if remainder > 0:
        if remainder < 10:
            parts.append(ones_list[remainder])
        elif remainder < 20:
            parts.append(teens_list[remainder - 10])
        else:
            t = remainder // 10  # عدد العشرات
            o = remainder % 10  # عدد الآحاد
            if o:
                parts.append(ones_list[o])
                parts.append(tens_list[t])
            else:
                parts.append(tens_list[t])

    return join_with_waw(parts)


# دالة تحويل رقم صحيح (من أي حجم) إلى نص عربي
def convert_number(n):
    if n == 0:
        return "صفر"

    parts = []

    # المليارات (إذا وجد)
    if n >= 1000000000:
        billions = n // 1000000000
        n %= 1000000000
        parts.append(convert_hundreds(billions) + " مليار")

    # الملايين
    if n >= 1000000:
        millions = n // 1000000
        n %= 1000000
        parts.append(convert_hundreds(millions) + " مليون")

    # الآلاف
    if n >= 1000:
        thousands = n // 1000
        n %= 1000
        if thousands == 1:
            parts.append("ألف")
        elif thousands == 2:
            parts.append("ألفان")
        elif 3 <= thousands <= 10:
            parts.append(convert_hundreds(thousands) + " آلاف")
        else:
            parts.append(convert_hundreds(thousands) + " ألف")

    # الأرقام من 0 إلى 999 (الباقي)
    if n > 0:
        parts.append(convert_hundreds(n))

    return join_with_waw(parts)
