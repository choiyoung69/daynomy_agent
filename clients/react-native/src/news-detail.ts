export type Keyword = {
  keyword: string;
  category: "PERSON" | "POLICY" | "EVENT" | "TERM" | "TREND";
  definition: string;
  context: string;
  watchPoint: string;
};
export type NewsSource = { name: string; url: string };
export type NewsArticle = {
  id: number;
  title: string;
  category: string;
  publishedAt: string | null;
  paragraphs: string[];
  imageUrl: string | null;
  sources: NewsSource[];
  imageCredit: NewsSource | null;
};
export type KeywordPart = { text: string; keyword?: Keyword };
const record = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
export const newsCategories: Record<string, string> = {
  ALL: "전체",
  REAL_ESTATE: "부동산",
  DEPOSIT_SAVINGS: "예·적금",
  STOCK: "주식",
  ECONOMY: "경제",
  ETF: "ETF",
  BOND: "채권",
  PENSION: "연금",
  FOREIGN_EXCHANGE: "외환",
  VIRTUAL_ASSET: "가상자산",
  GOLD: "금",
};
export const keywordCategories: Record<Keyword["category"], string> = {
  PERSON: "인물",
  POLICY: "정책",
  EVENT: "사건",
  TERM: "용어",
  TREND: "흐름",
};
function textContent(value: string): string[] {
  return value
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<br\s*\/?\s*>|<\/(?:p|div|li|h[1-6])>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(
      /&(?:nbsp|amp|lt|gt|quot|apos);/g,
      (e) =>
        ({
          "&nbsp;": " ",
          "&amp;": "&",
          "&lt;": "<",
          "&gt;": ">",
          "&quot;": '"',
          "&apos;": "'",
        })[e]!,
    )
    .split(/\r?\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}
export function decodeArticle(raw: unknown): NewsArticle {
  if (
    !record(raw) ||
    !Number.isSafeInteger(raw.id) ||
    Number(raw.id) <= 0 ||
    typeof raw.title !== "string" ||
    typeof raw.category !== "string" ||
    !(raw.category in newsCategories) ||
    raw.category === "ALL" ||
    !(raw.publishedAt === null || typeof raw.publishedAt === "string") ||
    !(
      typeof raw.content === "string" ||
      (Array.isArray(raw.content) &&
        raw.content.every((p) => typeof p === "string"))
    ) ||
    !Array.isArray(raw.sources) ||
    !raw.sources.every(
      (s) =>
        record(s) && typeof s.name === "string" && typeof s.url === "string",
    ) ||
    !(
      raw.imageUrl === undefined ||
      raw.imageUrl === null ||
      typeof raw.imageUrl === "string"
    )
  )
    throw new Error("뉴스 상세 응답 형식이 올바르지 않습니다.");
  const credit = raw.imageSource;
  return {
    id: raw.id as number,
    title: raw.title,
    category: raw.category,
    publishedAt: raw.publishedAt as string | null,
    paragraphs: (typeof raw.content === "string"
      ? [raw.content]
      : (raw.content as string[])
    ).flatMap(textContent),
    imageUrl: (raw.imageUrl as string) ?? null,
    sources: raw.sources as NewsSource[],
    imageCredit:
      record(credit) &&
      typeof credit.name === "string" &&
      credit.name.trim() &&
      typeof credit.url === "string"
        ? { name: credit.name, url: credit.url }
        : null,
  };
}
export function decodeKeywords(raw: unknown): Keyword[] {
  if (
    !record(raw) ||
    !Array.isArray(raw.keywords) ||
    !raw.keywords.every(
      (k) =>
        record(k) &&
        typeof k.keyword === "string" &&
        k.keyword.trim() &&
        typeof k.category === "string" &&
        k.category in keywordCategories &&
        ["definition", "context", "watchPoint"].every(
          (field) => typeof k[field] === "string",
        ),
    )
  )
    throw new Error("키워드 분석 응답 형식이 올바르지 않습니다.");
  return [
    ...new Map((raw.keywords as Keyword[]).map((k) => [k.keyword, k])).values(),
  ];
}
export function keywordParagraphs(
  paragraphs: string[],
  keywords: Keyword[],
): KeywordPart[][] {
  const ordered = [...keywords]
      .filter((k) => k.keyword)
      .sort((a, b) => b.keyword.length - a.keyword.length),
    used = new Set<string>();
  return paragraphs.map((text) => {
    const parts: KeywordPart[] = [];
    let plain = "";
    let i = 0;
    while (i < text.length) {
      const found = ordered.find(
        (k) => !used.has(k.keyword) && text.startsWith(k.keyword, i),
      );
      if (!found) {
        plain += text[i++];
        continue;
      }
      if (plain) {
        parts.push({ text: plain });
        plain = "";
      }
      parts.push({ text: found.keyword, keyword: found });
      used.add(found.keyword);
      i += found.keyword.length;
    }
    if (plain) parts.push({ text: plain });
    return parts;
  });
}
export function safeNewsUrl(
  value: string | null,
  base?: string,
): string | null {
  if (!value || /[\u0000-\u0020\u007f]/.test(value)) return null;
  try {
    const url = new URL(value, base);
    if (url.username || url.password) return null;
    if (
      url.protocol === "https:" ||
      (url.protocol === "http:" &&
        ["localhost", "127.0.0.1", "10.0.2.2", "[::1]"].includes(url.hostname))
    )
      return url.href;
  } catch {}
  return null;
}
