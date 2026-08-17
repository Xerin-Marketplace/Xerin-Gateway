import type { ReactNode } from "react";

type PaymentsPageShellProps = {
  title: string;
  description: string;
  children: ReactNode;
  actions?: ReactNode;
  embedded?: boolean;
};

export default function PaymentsPageShell({
  title,
  description,
  children,
  actions,
  embedded = false,
}: PaymentsPageShellProps) {
  return (
    <div className="min-w-0 space-y-5">
      <header className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {!embedded ? (
              <>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#f47524]">
                  Admin / Payments
                </p>
                <h1 className="mt-2 text-2xl font-semibold text-gray-900">
                  {title}
                </h1>
              </>
            ) : null}
            <p
              className={`${embedded ? "" : "mt-2"} max-w-2xl text-sm text-gray-600`}
            >
              {description}
            </p>
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      </header>
      {children}
    </div>
  );
}
