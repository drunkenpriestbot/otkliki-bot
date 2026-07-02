/**
 * Telegram webhook (Cloudflare Workers, бесплатный тариф, без карты, всегда включён).
 *
 * Два независимых сценария:
 *
 * 1. Reply на сообщение бота со своим отредактированным текстом отклика —
 *    воркер достаёт ссылку на заказ из исходного сообщения (через regex) и
 *    прикрепляет такую же кнопку "Перейти к заказу" к отредактированному
 *    сообщению — без отдельной базы данных.
 *
 * 2. Нажатие кнопки "Сгенерировать отклик"/"Удалить" под превью-карточкой
 *    (preview_notify.py) — воркер сразу убирает кнопки и шлёт toast
 *    ("Генерирую…"/"Удалено"), затем дёргает GitHub Actions
 *    (workflow_dispatch на monitor.yml) с inputs.action=generate/delete и
 *    inputs.candidate_id из callback_data. Сама генерация черновика и его
 *    отправка происходят уже внутри workflow (generate_one.py/notify.py) —
 *    воркер только маршрутизирует нажатие, ничего не хранит сам.
 *
 * ORDER_URL_RE ниже настроен на ссылки вида https://t.me/<канал>/<id>
 * (формат ссылок из monitor_telegram.py) — поменяй regex, если источник заказов
 * другой (своя биржа, другой формат ссылок).
 *
 * Секреты воркера (wrangler secret put):
 * - TELEGRAM_BOT_TOKEN — токен бота.
 * - GITHUB_PAT — fine-grained PAT с правом Actions: Read and write только на
 *   репозиторий otkliki-bot (тот же, что у cron-job.org).
 * Переменная (wrangler.toml, не секрет): GITHUB_REPO = "owner/repo".
 */

const ORDER_URL_RE = /https:\/\/t\.me\/[\w]+\/\d+/;

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("ok", { status: 200 });
    }

    const update = await request.json();

    if (update.callback_query) {
      return handleCallback(update.callback_query, env);
    }

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

async function handleCallback(callbackQuery, env) {
  const data = callbackQuery.data || "";
  const sep = data.indexOf(":");
  if (sep === -1) {
    return new Response("bad callback_data", { status: 200 });
  }
  const action = data.slice(0, sep); // "gen" | "del"
  const candidateId = data.slice(sep + 1);

  const ackText =
    action === "gen" ? "Генерирую черновик…" : action === "del" ? "Удалено" : "ОК";

  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQuery.id, text: ackText }),
  });

  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: callbackQuery.message.chat.id,
      message_id: callbackQuery.message.message_id,
      reply_markup: { inline_keyboard: [] },
    }),
  });

  if (action === "gen" || action === "del") {
    await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/monitor.yml/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_PAT}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "otkliki-bot-worker",
        },
        body: JSON.stringify({
          ref: "main",
          inputs: {
            action: action === "gen" ? "generate" : "delete",
            candidate_id: candidateId,
          },
        }),
      }
    );
  }

  return new Response("ok", { status: 200 });
}
