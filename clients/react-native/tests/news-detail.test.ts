import test from "node:test";
import assert from "node:assert/strict";
import {
  decodeArticle,
  decodeKeywords,
  keywordParagraphs,
  safeNewsUrl,
} from "../src/news-detail.ts";
const raw = {
  id: 52,
  title: "경제 소식",
  category: "STOCK",
  publishedAt: null,
  imageUrl: null,
  content: "금리 인상\n\n환율 변동",
  sources: [{ name: "출처", url: "https://example.com/article" }],
};
const keyword = {
  keyword: "금리",
  category: "TERM" as const,
  definition: "자금을 빌린 대가의 비율",
  context: "합성 검사 문장의 금리",
  watchPoint: "변경 시점을 확인",
};
test("본문 문자열은 실제 문단으로 읽고 날짜·사진 null을 보존한다", () => {
  const a = decodeArticle(raw);
  assert.deepEqual(a.paragraphs, ["금리 인상", "환율 변동"]);
  assert.equal(a.publishedAt, null);
  assert.equal(a.imageUrl, null);
});
test("원본 content 배열도 전체 문단을 보존한다", () =>
  assert.deepEqual(
    decodeArticle({ ...raw, content: ["첫 문단", "두 문단\n\n세 문단"] })
      .paragraphs,
    ["첫 문단", "두 문단", "세 문단"],
  ));
test("빈 본문을 가짜 문장으로 채우지 않는다", () =>
  assert.deepEqual(decodeArticle({ ...raw, content: "  \n " }).paragraphs, []));
test("본문에 HTML이 있으면 문단 경계와 엔티티를 보존한 텍스트로 읽는다", () =>
  assert.deepEqual(
    decodeArticle({ ...raw, content: "<p>A &amp; B</p><p>두 번째<br>줄</p>" })
      .paragraphs,
    ["A & B", "두 번째", "줄"],
  ));
test("기사의 잘못된 필수 필드는 명시적으로 거절한다", () => {
  for (const patch of [
    { id: 0 },
    { title: 4 },
    { content: { body: "본문" } },
    { sources: [{ url: 23 }] },
    { category: "UNKNOWN" },
  ])
    assert.throws(() => decodeArticle({ ...raw, ...patch }));
});
test("이미지 출처는 제공된 이름과 URL만 사용한다", () =>
  assert.deepEqual(
    decodeArticle({
      ...raw,
      imageSource: {
        type: "MANUAL",
        name: "제공처",
        url: "https://example.com/photo",
        author: "",
        license: "",
        licenseUrl: "",
      },
    }).imageCredit,
    { name: "제공처", url: "https://example.com/photo" },
  ));
test("키워드 응답의 뜻·맥락·확인할 점을 그대로 읽는다", () =>
  assert.deepEqual(decodeKeywords({ keywords: [keyword] }), [keyword]));
test("빈 키워드는 정상 미제공 상태다", () =>
  assert.deepEqual(decodeKeywords({ keywords: [] }), []));
test("잘못된 키워드 응답을 빈 분석으로 숨기지 않는다", () => {
  for (const raw of [
    {},
    { keywords: ["금리"] },
    { keywords: [{ ...keyword, watchPoint: null }] },
    { keywords: [{ ...keyword, category: "UNKNOWN" }] },
  ])
    assert.throws(() => decodeKeywords(raw));
});
test("본문 첫 등장 키워드만 강조하고 긴 표현을 우선한다", () => {
  const long = { ...keyword, keyword: "기준금리" };
  const parts = keywordParagraphs(
    ["기준금리와 금리, 기준금리", "금리 설명"],
    [keyword, long],
  );
  assert.deepEqual(
    parts
      .flat()
      .filter((p) => p.keyword)
      .map((p) => p.text),
    ["기준금리", "금리"],
  );
  assert.deepEqual(
    parts.map((p) => p.map((x) => x.text).join("")),
    ["기준금리와 금리, 기준금리", "금리 설명"],
  );
});
test("정규식 기호가 든 키워드는 본문을 손상시키지 않는다", () =>
  assert.equal(
    keywordParagraphs(["A+B 정책"], [{ ...keyword, keyword: "A+B" }])[0][0]
      .keyword?.keyword,
    "A+B",
  ));
test("본문에 없는 키워드와 중복 항목은 본문에 삽입하지 않는다", () => {
  const parts = keywordParagraphs(
    ["금리 설명"],
    [keyword, keyword, { ...keyword, keyword: "없는 말" }],
  );
  assert.equal(parts.flat().filter((p) => p.keyword).length, 1);
});
test("안전한 상대 이미지 URL과 HTTPS 외부 링크만 해석한다", () => {
  assert.equal(
    safeNewsUrl("/images/photo.jpg", "http://10.0.2.2:18109"),
    "http://10.0.2.2:18109/images/photo.jpg",
  );
  assert.equal(
    safeNewsUrl("https://example.com/article"),
    "https://example.com/article",
  );
  for (const url of [
    "javascript:alert(1)",
    "https://user:pass@example.com",
    "file:///tmp/a",
    "http://external.example/a",
    "https://example.com\n/a",
  ])
    assert.equal(safeNewsUrl(url), null);
});
