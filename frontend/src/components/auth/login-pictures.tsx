// The pictures beside a login form (SPEC F02 rule 12, D-182): a Pattern and a
// People illustration drawn here in the school's colour (so there is no image
// to download and no licence to worry about), or the school's own photo.
// Phones never get the picture: the frame hides it, and the photo is only
// requested on screens at least 48rem wide (the <picture> source), so pupils
// on prepaid data don't pay for it.

export type Picture = "pattern" | "people" | "photo";

function PatternPicture({ colour }: { colour: string }) {
  return (
    <svg
      viewBox="0 0 800 1000"
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 size-full"
      aria-hidden="true"
    >
      <rect width="800" height="1000" style={{ fill: colour }} />
      <g fill="none" stroke="#fff" strokeOpacity="0.14" strokeWidth="2">
        {[120, 200, 280, 360, 440, 520].map((r) => (
          <circle key={r} cx="640" cy="180" r={r} />
        ))}
      </g>
      <g fill="#fff" fillOpacity="0.12">
        {Array.from({ length: 10 }, (_, row) =>
          Array.from({ length: 8 }, (_, col) => (
            <circle
              key={`${row}-${col}`}
              cx={60 + col * 34}
              cy={560 + row * 34}
              r="4"
            />
          )),
        )}
      </g>
      <path
        d="M0 860 Q200 760 400 860 T800 860 V1000 H0Z"
        fill="#000"
        fillOpacity="0.12"
      />
      <rect
        x="520"
        y="620"
        width="180"
        height="180"
        rx="36"
        fill="#fff"
        fillOpacity="0.1"
        transform="rotate(14 610 710)"
      />
    </svg>
  );
}

function PeoplePicture({ colour }: { colour: string }) {
  return (
    <svg
      viewBox="0 0 800 1000"
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 size-full"
      aria-hidden="true"
    >
      <rect width="800" height="1000" style={{ fill: colour }} />
      <rect width="800" height="1000" fill="#fff" fillOpacity="0.82" />
      <circle
        cx="400"
        cy="560"
        r="300"
        style={{ fill: colour }}
        fillOpacity="0.18"
      />
      {/* A pupil in uniform holding a book. */}
      <rect
        x="250"
        y="560"
        width="150"
        height="260"
        rx="60"
        style={{ fill: colour }}
      />
      <rect x="270" y="800" width="40" height="150" rx="16" fill="#3b2a20" />
      <rect x="340" y="800" width="40" height="150" rx="16" fill="#3b2a20" />
      <circle cx="325" cy="480" r="70" fill="#8a5a3c" />
      <path
        d="M258 470 Q325 380 392 470 Q370 420 325 418 Q280 420 258 470Z"
        fill="#1f140e"
      />
      <rect
        x="300"
        y="640"
        width="90"
        height="70"
        rx="6"
        fill="#fff"
        transform="rotate(-8 345 675)"
      />
      {/* A taller pupil, waving. */}
      <rect
        x="430"
        y="520"
        width="160"
        height="300"
        rx="64"
        fill="#fff"
        style={{ stroke: colour }}
        strokeWidth="6"
      />
      <rect x="455" y="800" width="42" height="160" rx="16" fill="#22324a" />
      <rect x="525" y="800" width="42" height="160" rx="16" fill="#22324a" />
      <circle cx="510" cy="440" r="72" fill="#6b4430" />
      <path
        d="M440 430 Q510 340 582 430 Q560 380 510 376 Q462 380 440 430Z"
        fill="#120c08"
      />
      <rect
        x="575"
        y="430"
        width="34"
        height="150"
        rx="17"
        fill="#6b4430"
        transform="rotate(20 592 505)"
      />
      <g style={{ fill: colour }} fillOpacity="0.5">
        <path d="M150 260 l12 26 28 4 -20 20 5 28 -25 -13 -25 13 5 -28 -20 -20 28 -4z" />
        <path d="M650 250 l8 18 20 3 -14 14 3 20 -17 -9 -17 9 3 -20 -14 -14 20 -3z" />
      </g>
    </svg>
  );
}

// A 1x1 transparent GIF: what phones get instead of the photo.
const NOTHING =
  "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

function PhotoPicture({ url }: { url: string }) {
  return (
    <picture>
      <source media="(min-width: 48rem)" srcSet={url} />
      <img
        src={NOTHING}
        alt=""
        className="absolute inset-0 size-full object-cover"
      />
    </picture>
  );
}

export function LoginPicture({
  picture,
  colour,
  photoUrl,
}: {
  picture: Picture;
  colour: string;
  photoUrl: string | null;
}) {
  return (
    <>
      {picture === "photo" && photoUrl ? (
        <PhotoPicture url={photoUrl} />
      ) : picture === "people" ? (
        <PeoplePicture colour={colour} />
      ) : (
        <PatternPicture colour={colour} />
      )}
      {/* Dark mode: dim the picture a little so it does not glare. */}
      <div
        className="absolute inset-0 bg-black/0 dark:bg-black/30"
        aria-hidden="true"
      />
    </>
  );
}

// Words over a light picture (people, photo) need a dark shade behind them.
export function needsShade(picture: Picture): boolean {
  return picture !== "pattern";
}
