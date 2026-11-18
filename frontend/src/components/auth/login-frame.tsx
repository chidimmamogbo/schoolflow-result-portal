// The frame of every page before login (SPEC F02 rules 12 and 13, D-182): on
// tablets and laptops a split screen in the school's chosen layout, "Half and
// half" (picture beside the form) or "Picture behind" (the picture fills the
// screen and the form sits in a card); on phones only the logo, the name and
// the form. Chosen in the prototype on branch prototype/school-login.
import type { ReactNode } from "react";

import { LoginPicture, type Picture, needsShade } from "./login-pictures";

export type LoginBrand = {
  name: string;
  // The school's code (the logo stand-in shows it); null for SchoolFlow itself.
  code: string | null;
  colour: string;
  logoUrl: string | null;
  message: string | null;
  layout: "half" | "behind";
  picture: Picture;
  photoUrl: string | null;
};

export const SCHOOLFLOW: LoginBrand = {
  name: "SchoolFlow",
  code: null,
  colour: "var(--primary)",
  logoUrl: null,
  message: null,
  layout: "half",
  picture: "pattern",
  photoUrl: null,
};

function Logo({ brand, size }: { brand: LoginBrand; size: "md" | "lg" }) {
  const box = size === "lg" ? "size-20 text-2xl" : "size-12 text-base";
  if (brand.logoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- the school's own uploaded logo
      <img
        src={brand.logoUrl}
        alt={`${brand.name} logo`}
        className={`${box} rounded-md object-contain`}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`${box} flex items-center justify-center rounded-md font-bold text-white`}
      style={{ background: brand.colour }}
    >
      {brand.code ?? "SF"}
    </span>
  );
}

function Words({ brand, big }: { brand: LoginBrand; big?: boolean }) {
  return (
    <>
      <p className={`${big ? "text-5xl" : "text-4xl"} leading-tight font-bold`}>
        {brand.name}
      </p>
      <p className={`mt-3 max-w-md ${big ? "text-xl" : "text-lg"} opacity-90`}>
        {brand.message ?? `Welcome to ${brand.name}`}
      </p>
    </>
  );
}

function FormPart({
  title,
  intro,
  children,
}: {
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <>
      <h1 className="mb-1 text-2xl font-bold">{title}</h1>
      {intro ? (
        <div className="mb-6 text-muted">{intro}</div>
      ) : (
        <div className="mb-4" />
      )}
      {children}
    </>
  );
}

function PoweredBy() {
  return <p className="text-sm text-muted">Powered by SchoolFlow</p>;
}

export function LoginFrame({
  brand,
  title,
  intro,
  children,
}: {
  brand: LoginBrand;
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  const picture = (
    <LoginPicture
      picture={brand.picture}
      colour={brand.colour}
      photoUrl={brand.photoUrl}
    />
  );
  if (brand.layout === "behind") {
    return (
      <main className="relative min-h-screen overflow-hidden bg-bg">
        <div className="absolute inset-0 hidden md:block">
          {picture}
          <div className="absolute inset-0 bg-gradient-to-r from-black/55 via-black/20 to-transparent" />
        </div>
        <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center gap-10 px-4 py-10 md:flex-row md:justify-between md:px-10">
          <div className="hidden max-w-md text-white md:block">
            <Words brand={brand} big />
          </div>
          <section className="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-lg md:p-8">
            <div className="mb-6 flex items-center gap-3">
              <Logo brand={brand} size="md" />
              <p className="font-bold">{brand.name}</p>
            </div>
            <FormPart title={title} intro={intro}>
              {children}
            </FormPart>
            <div className="mt-6 text-center">
              <PoweredBy />
            </div>
          </section>
        </div>
      </main>
    );
  }
  return (
    <main className="grid min-h-screen bg-bg md:grid-cols-2">
      <section className="relative hidden overflow-hidden md:block">
        {picture}
        <div
          className={`absolute inset-x-0 bottom-0 p-10 text-white ${
            needsShade(brand.picture)
              ? "bg-gradient-to-t from-black/75 via-black/35 to-transparent"
              : ""
          }`}
        >
          <Words brand={brand} />
        </div>
      </section>
      <section className="flex flex-col items-center justify-center gap-8 px-4 py-10 md:px-10">
        <div className="flex flex-col items-center gap-3 text-center">
          <Logo brand={brand} size="lg" />
          <p className="text-lg font-bold md:hidden">{brand.name}</p>
        </div>
        <div className="w-full max-w-sm">
          <FormPart title={title} intro={intro}>
            {children}
          </FormPart>
        </div>
        <PoweredBy />
      </section>
    </main>
  );
}
