import Link from "next/link";
import type { MarketplacePolicy } from "@/content/marketplacePolicies";

type PolicyPageProps = {
  policy: MarketplacePolicy;
};

export default function PolicyPage({ policy }: PolicyPageProps) {
  return (
    <main className="bg-gray-1 py-12 dark:bg-darkTheme-bg sm:py-16">
      <article className="mx-auto max-w-[900px] px-4 sm:px-8">
        <nav className="mb-6 text-sm text-dark-4 dark:text-darkTheme-body-color">
          <Link href="/" className="transition-colors hover:text-blue">
            Home
          </Link>
          <span aria-hidden="true" className="mx-2">
            /
          </span>
          <span>Marketplace Policies &amp; Legal</span>
        </nav>

        <header className="rounded-2xl bg-dark px-6 py-9 text-white shadow-1 sm:px-10 sm:py-12">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.16em] text-[#ff6c2f]">
            Xerin Marketplace
          </p>
          <h1 className="text-3xl font-bold sm:text-4xl">{policy.title}</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-white/75">
            {policy.summary}
          </p>
        </header>

        <div className="mt-8 space-y-6">
          {policy.sections.map((section) => (
            <section
              key={section.heading}
              className="rounded-2xl border border-gray-3 bg-white p-6 shadow-sm dark:border-darkTheme-border dark:bg-darkTheme-card sm:p-8"
            >
              <h2 className="mb-4 text-xl font-semibold text-dark dark:text-white">
                {section.heading}
              </h2>

              {section.paragraphs?.map((paragraph) => (
                <p
                  key={paragraph}
                  className="mb-4 last:mb-0 leading-7 text-dark-4 dark:text-darkTheme-body-color"
                >
                  {paragraph}
                </p>
              ))}

              {section.bullets ? (
                <ul className="mt-4 list-disc space-y-2 pl-5 leading-7 text-dark-4 marker:text-[#ff6c2f] dark:text-darkTheme-body-color">
                  {section.bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </div>

        <aside className="mt-8 rounded-2xl border border-[#ff6c2f]/30 bg-[#ff6c2f]/5 p-6 text-dark dark:text-white sm:p-8">
          <h2 className="text-lg font-semibold">Need help or clarification?</h2>
          <p className="mt-2 leading-7 text-dark-4 dark:text-darkTheme-body-color">
            Contact Xerin customer support at{" "}
            <a
              href="mailto:support@xerin.co.tz"
              className="font-semibold text-[#e85d24] hover:underline"
            >
              support@xerin.co.tz
            </a>
            .
          </p>
        </aside>
      </article>
    </main>
  );
}

