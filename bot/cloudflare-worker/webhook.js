/**
 * Telegram webhook (Cloudflare Workers, бесплатный тариф, без карты, всегда включён).
 *
 * Когда ты отвечаешь (Reply) на сообщение бота со своим отредактированным
 * текстом отклика, Telegram присылает сюда update с message.reply_to_message — это
 * оригинальное уведомление, в котором уже есть ссылка на заказ. Воркер достаёт
 * ссылку через regex и прикрепляет такую же кнопку "Перейти к заказу" к
 * отредактированному сообщению — без отдельной базы данных, ссылка и так
 * лежит в тексте исходного сообщения.
 *
 * ORDER_URL_RE ниже настроен на ссылки вида https://t.me/<канал>/<id>
 * (формат ссылок из monitor_telegram.py) — поменяй regex, если источник заказов
 * другой (своя биржа, другой формат ссылок).
 *
 * TELEGRAM_BOT_TOKEN передаётся как секрет окружения Worker'а (wrangler secret put).
 */

const ORDER_URL_RE = /https:\/\/t\.me\/[\w]+\/\d+/;

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("ok", { status: 200 });
    }

    const update = await request.json();
    const message = update.message;

    if (!message || !message.reply_to_message) {
      return new Response("ignored", { status: 200 });
    }

    const originalText = message.reply_to_message.text || "";
    const match = originalText.match(ORDER_URL_RE);
    if (!match) {
      return new Response("no url found", { status: 200 });
    }

    const projectUrl = match[0];

    await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: message.chat.id,
          text: "✏️ Отредактированный вариант",
          reply_to_message_id: message.message_id,
          reply_markup: {
            inline_keyboard: [[{ text: "🔗 Перейти к заказу", url: projectUrl }]],
          },
        }),
      }
    );

    return new Response("ok", { status: 200 });
  },
};
