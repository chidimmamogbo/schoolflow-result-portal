// How money and dates are shown everywhere (design rules): "₦321,000", "5 Jan 2027".
// Money arrives from the API as whole kobo (integers), never a float.

export function money(kobo: number): string {
  const naira = kobo / 100;
  const shown = Number.isInteger(naira)
    ? naira.toLocaleString("en-NG")
    : naira.toLocaleString("en-NG", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
  return `₦${shown}`;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const LAGOS_OFFSET_MS = 60 * 60 * 1000; // West Africa Time is UTC+1 all year.

function parts(value: string | Date): {
  day: number;
  month: number;
  year: number;
  time: Date;
} {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number) as [
      number,
      number,
      number,
    ];
    return {
      day,
      month: month - 1,
      year,
      time: new Date(Date.UTC(year, month - 1, day)),
    };
  }
  const time = new Date(new Date(value).getTime() + LAGOS_OFFSET_MS);
  return {
    day: time.getUTCDate(),
    month: time.getUTCMonth(),
    year: time.getUTCFullYear(),
    time,
  };
}

export function date(value: string | Date): string {
  const { day, month, year } = parts(value);
  return `${day} ${MONTHS[month]} ${year}`;
}

export function dateTime(value: string | Date): string {
  const { time } = parts(value);
  const hh = String(time.getUTCHours()).padStart(2, "0");
  const mm = String(time.getUTCMinutes()).padStart(2, "0");
  return `${date(value)}, ${hh}:${mm}`;
}
