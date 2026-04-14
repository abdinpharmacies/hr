import telebot

BOT_TOKEN = '5589615908:AAGUpFRgyCkladAjXWe-rSiSiNHOblNwyIM'
bot = telebot.TeleBot(BOT_TOKEN)

bot.send_message(-1002128909908, """
#####  متابعة طلب العهدة رقم 1908 #####

 الموظف: محمود عبد اللاه دسوقي علي - 279
المدير: ابتهال رفعت محمدين مهران - 4029
حالة العهدة: تم الصرف
 للمتابعة، برجاء الدخول علي رابط العهدة التالي:   

By محمد عبدالمنعم محمد عبدالرحمن
Goto Link ⏩ (https://co.abdinpharmacies.com/web#id=1908&model=ab_custody_request_header&view_type=form)""")
