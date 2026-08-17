import { formatCurrency } from "@/lib/formatCurrency";
import type { Order, Payment } from "@/types/api/commerce";
import type { Address } from "@/types/api/user";

const brandColor = "#f7941d";

const escapeHtml = (unsafe: string): string =>
  unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

const orderItemsHtml = (order: Order): string => {
  return order.items
    .map(
      (item) => `
    <tr>
      <td style="padding:10px;border-bottom:1px solid #e2e8f0;">${escapeHtml(item.product_name)}${item.variant_name ? `<br><small>${escapeHtml(item.variant_name)}</small>` : ""}</td>
      <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:center;">${item.quantity}</td>
      <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;">${formatCurrency(item.unit_price, order.currency)}</td>
      <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;">${formatCurrency(item.total_price, order.currency)}</td>
    </tr>
  `,
    )
    .join("");
};

const totalsHtml = (order: Order): string => `
  <div style="margin-top:20px;text-align:right;">
    <p><strong>Subtotal:</strong> ${formatCurrency(order.subtotal, order.currency)}</p>
    <p><strong>Shipping:</strong> ${formatCurrency(order.shipping_amount, order.currency)}</p>
    <p><strong>Tax:</strong> ${formatCurrency(order.tax_amount, order.currency)}</p>
    ${order.discount_amount && Number(order.discount_amount) > 0 ? `<p><strong>Discount:</strong> -${formatCurrency(order.discount_amount, order.currency)}</p>` : ""}
    <p style="font-size:1.2em;color:${brandColor};"><strong>Total:</strong> ${formatCurrency(order.total, order.currency)}</p>
  </div>
`;

const baseDocument = (title: string, body: string): string => `
  <!DOCTYPE html>
  <html>
    <head>
      <meta charset="utf-8">
      <title>${escapeHtml(title)}</title>
      <style>
        body { font-family: Arial, sans-serif; color: #1f2937; padding: 40px; max-width: 800px; margin: 0 auto; }
        h1 { color: ${brandColor}; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #f8fafc; text-align: left; padding: 10px; border-bottom: 2px solid #e2e8f0; }
        .muted { color: #64748b; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #f1f5f9; font-size: 0.85em; text-transform: capitalize; }
      </style>
    </head>
    <body>
      ${body}
    </body>
  </html>
`;

export const printOrderInvoice = (
  order: Order,
  address?: Address | null,
  payment?: Payment | null,
) => {
  const orderDate = order.created_at
    ? new Date(order.created_at).toLocaleString()
    : "—";
  const body = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
      <div>
        <h1>Xerin Market Invoice</h1>
        <p class="muted">Order #${order.id.slice(0, 12).toUpperCase()}</p>
      </div>
      <div style="text-align:right;">
        <p><span class="badge">${order.status.replaceAll("_", " ")}</span></p>
        <p class="muted">${orderDate}</p>
      </div>
    </div>

    <div style="margin-top:30px;">
      <h3>Bill To</h3>
      <p class="muted">${address ? escapeHtml(`${address.street}, ${address.city}, ${address.region}, ${address.country}`) : "Address on file"}</p>
    </div>

    ${payment ? `
    <div style="margin-top:20px;">
      <h3>Payment</h3>
      <p class="muted">Method: ${(payment.provider || payment.method || "—").replaceAll("_", " ")}</p>
      <p class="muted">Status: ${payment.status.replaceAll("_", " ")}</p>
      <p class="muted">Reference: ${payment.provider_transaction_id || payment.id.slice(0, 8)}</p>
    </div>
    ` : ""}

    <table>
      <thead>
        <tr>
          <th>Product</th>
          <th style="text-align:center;">Qty</th>
          <th style="text-align:right;">Unit Price</th>
          <th style="text-align:right;">Total</th>
        </tr>
      </thead>
      <tbody>
        ${orderItemsHtml(order)}
      </tbody>
    </table>

    ${totalsHtml(order)}

    <p style="margin-top:40px;font-size:0.85em;" class="muted">Thank you for shopping with Xerin Market.</p>
  `;

  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(baseDocument(`Invoice ${order.id}`, body));
  w.document.close();
  w.focus();
  w.print();
};

export const printPaymentReceipt = (payment: Payment) => {
  const paymentDate = payment.paid_at
    ? new Date(payment.paid_at).toLocaleString()
    : payment.created_at
      ? new Date(payment.created_at).toLocaleString()
      : "—";

  const body = `
    <div style="text-align:center;">
      <h1>Xerin Market Receipt</h1>
      <p class="muted">Payment Reference: ${payment.provider_transaction_id || payment.id.slice(0, 12).toUpperCase()}</p>
    </div>

    <div style="margin-top:30px;">
      <p><strong>Order:</strong> #${payment.order_id.slice(0, 12).toUpperCase()}</p>
      <p><strong>Amount:</strong> ${formatCurrency(payment.amount, payment.currency)}</p>
      <p><strong>Method:</strong> ${(payment.provider || payment.method || "—").replaceAll("_", " ")}</p>
      <p><strong>Status:</strong> <span class="badge">${payment.status.replaceAll("_", " ")}</span></p>
      <p><strong>Date:</strong> ${paymentDate}</p>
    </div>

    <p style="margin-top:40px;font-size:0.85em;" class="muted">This is an official receipt for your records.</p>
  `;

  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(baseDocument(`Receipt ${payment.id}`, body));
  w.document.close();
  w.focus();
  w.print();
};
