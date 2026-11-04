import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import type { APIClient } from "../api";
import {
  decodeArticle,
  decodeKeywords,
  keywordParagraphs,
  newsCategories,
  keywordCategories,
  safeNewsUrl,
} from "../news-detail";
import type { Keyword, NewsArticle } from "../news-detail";
import { Button, s } from "./kit";
import { theme as c } from "./theme";

function message(error: unknown) {
  return error instanceof TypeError
    ? "서버에 연결하지 못했습니다. 잠시 후 다시 조회해 주세요."
    : error instanceof Error
      ? error.message
      : "정보를 불러오지 못했습니다.";
}
function useResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: React.DependencyList,
) {
  const [state, setState] = useState<{
    data: T | null;
    error: string;
    loading: boolean;
  }>({ data: null, error: "", loading: true });
  const [attempt, retry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let live = true;
    setState({ data: null, error: "", loading: true });
    load(controller.signal)
      .then((data) => {
        if (live) setState({ data, error: "", loading: false });
      })
      .catch((e) => {
        if (live) setState({ data: null, error: message(e), loading: false });
      });
    return () => {
      live = false;
      controller.abort();
    };
  }, [...deps, attempt]);
  return { ...state, retry: () => retry((n) => n + 1) };
}
function LoadState({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error: string;
  retry: () => void;
}) {
  return loading ? (
    <View style={st.loading}>
      <ActivityIndicator color={c.accent} />
      <Text style={s.muted}>불러오고 있어요.</Text>
    </View>
  ) : error ? (
    <View style={{ gap: 12 }} accessibilityLiveRegion="polite">
      <Text style={{ color: c.danger }}>{error}</Text>
      <Button title="다시 조회" secondary onPress={retry} />
    </View>
  ) : null;
}
function openSource(url: string) {
  const safe = safeNewsUrl(url);
  if (!safe) return;
  void Linking.openURL(safe).catch(() =>
    Alert.alert("원문을 열 수 없습니다", "연결 상태를 확인해 주세요."),
  );
}
function ArticlePhoto({
  article,
  base,
}: {
  article: NewsArticle;
  base: string;
}) {
  const [failed, setFailed] = useState(false);
  const uri = safeNewsUrl(article.imageUrl, base);
  if (!uri) return null;
  return (
    <View style={{ gap: 8 }}>
      {failed ? (
        <View style={st.photoMissing}>
          <Text style={s.muted}>사진을 불러오지 못했습니다.</Text>
        </View>
      ) : (
        <Image
          source={{ uri }}
          style={st.photo}
          accessibilityLabel="기사 사진"
          onError={() => setFailed(true)}
        />
      )}
      {article.imageCredit && (
        <Text style={st.credit}>사진 제공 · {article.imageCredit.name}</Text>
      )}
    </View>
  );
}
export function NewsDetail({
  api,
  id,
  onClose,
}: {
  api: APIClient;
  id: number;
  onClose: () => void;
}) {
  const article = useResource(
    async (signal) =>
      decodeArticle(await api.call("newsDetail", { id, signal })),
    [api, id],
  );
  const keywords = useResource(
    async (signal) =>
      decodeKeywords(await api.call("keywords", { id, signal })),
    [api, id],
  );
  const analysis = useResource(
    async (signal) => {
      try {
        const raw: any = await api.call("marketAnalysis", { id, signal });
        if (
          !raw ||
          typeof raw.risk !== "string" ||
          typeof raw.watchPoint !== "string"
        )
          throw new Error("시장 분석 응답 형식이 올바르지 않습니다.");
        return raw as { risk: string; watchPoint: string };
      } catch (error: any) {
        if (
          error.status === 404 &&
          [
            "MARKET_ANALYSIS_NOT_FOUND",
            "NEWS_MARKET_ANALYSIS_NOT_FOUND",
          ].includes(error.code)
        )
          return null;
        throw error;
      }
    },
    [api, id],
  );
  const [selected, setSelected] = useState<Keyword | null>(null);
  const tokens = useMemo(
    () =>
      keywordParagraphs(article.data?.paragraphs ?? [], keywords.data ?? []),
    [article.data, keywords.data],
  );
  const [popover, setPopover] = useState<{ x: number; y: number } | null>(null);
  const { width, height } = useWindowDimensions();
  const closeAnalysis = () => {
    setSelected(null);
    setPopover(null);
  };
  const focusTarget = useRef<React.ElementRef<typeof Text> | null>(null);
  const showKeyword = (
    keyword: Keyword,
    target?: React.ElementRef<typeof Text> | null,
  ) => {
    focusTarget.current = target ?? null;
    if (Platform.OS === "web" && target) {
      target.measureInWindow((x, y) => {
        setPopover({ x, y });
        setSelected(keyword);
      });
    } else {
      setPopover(null);
      setSelected(keyword);
    }
  };
  useEffect(() => {
    setSelected(null);
    setPopover(null);
  }, [api, id]);
  useEffect(() => {
    if (Platform.OS !== "web" || !selected) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeAnalysis();
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [selected]);
  const news = article.data;
  return (
    <View style={{ flex: 1 }}>
      <View style={st.toolbar}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="뉴스 목록으로"
          onPress={onClose}
          style={st.back}
        >
          <Text style={{ fontSize: 16, color: c.ink }}>‹ 뉴스 목록으로</Text>
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={st.article}>
        <LoadState {...article} />
        {news && (
          <>
            <View style={st.meta}>
              <Text style={st.category}>{newsCategories[news.category]}</Text>
              {news.sources.map(
                (source, i) =>
                  safeNewsUrl(source.url) && (
                    <Pressable
                      key={`${source.url}:${i}`}
                      accessibilityRole="link"
                      onPress={() => openSource(source.url)}
                      style={st.source}
                    >
                      <Text style={s.muted}>{source.name} ↗</Text>
                    </Pressable>
                  ),
              )}
            </View>
            <Text accessibilityRole="header" style={st.headline}>
              {news.title}
            </Text>
            {!!news.publishedAt && (
              <Text style={s.muted}>
                {Number.isNaN(Date.parse(news.publishedAt))
                  ? news.publishedAt
                  : new Date(news.publishedAt).toLocaleString("ko-KR", {
                      timeZone: "Asia/Seoul",
                    })}
              </Text>
            )}
            <ArticlePhoto key={news.id} article={news} base={api.baseURL} />
            <View style={{ gap: 18 }} accessibilityLabel="뉴스 본문">
              {tokens.length ? (
                tokens.map((parts, index) => (
                  <Text key={index} style={st.body}>
                    {parts.map((part, i) =>
                      part.keyword ? (
                        <KeywordText
                          key={i}
                          keyword={part.keyword}
                          show={showKeyword}
                        />
                      ) : (
                        <Text key={i}>{part.text}</Text>
                      ),
                    )}
                  </Text>
                ))
              ) : (
                <Text style={s.muted}>
                  제공된 본문이 없습니다. 원문에서 기사 내용을 확인해 주세요.
                </Text>
              )}
            </View>
            <View style={st.section}>
              <Text accessibilityRole="header" style={s.heading}>
                키워드 분석
              </Text>
              <LoadState {...keywords} />
              {!!keywords.data?.length && (
                <>
                  <Text style={s.muted}>
                    본문의 파란 키워드나 아래 항목을 눌러 보세요.
                    {Platform.OS === "web"
                      ? " 마우스를 올려도 설명이 열립니다."
                      : ""}
                  </Text>
                  <View style={st.keywordList}>
                    {keywords.data.map((k) => (
                      <Pressable
                        key={k.keyword}
                        accessibilityRole="button"
                        accessibilityLabel={`${k.keyword} 키워드 분석`}
                        onPress={() => showKeyword(k)}
                        onHoverIn={() => showKeyword(k)}
                        style={st.keyword}
                      >
                        <Text style={{ color: c.accent, fontWeight: "600" }}>
                          {k.keyword}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                </>
              )}
              {!keywords.loading &&
                !keywords.error &&
                !keywords.data?.length && (
                  <Text style={s.muted}>
                    이 기사의 키워드 분석은 아직 제공되지 않았습니다.
                  </Text>
                )}
            </View>
            <View style={st.section}>
              <Text accessibilityRole="header" style={s.heading}>
                시장 분석
              </Text>
              <LoadState {...analysis} />
              {analysis.data ? (
                <>
                  <Text style={s.label}>위험 요인</Text>
                  <Text style={s.body}>{analysis.data.risk}</Text>
                  <Text style={s.label}>확인할 점</Text>
                  <Text style={s.body}>{analysis.data.watchPoint}</Text>
                </>
              ) : (
                !analysis.loading &&
                !analysis.error && (
                  <Text style={s.muted}>
                    이 기사의 시장 분석은 아직 제공되지 않았습니다.
                  </Text>
                )
              )}
            </View>
            {news.sources
              .filter((source) => safeNewsUrl(source.url))
              .map((source, i) => (
                <Button
                  key={i}
                  title={`${source.name} 원문 보기 ↗`}
                  secondary
                  onPress={() => openSource(source.url)}
                />
              ))}
          </>
        )}
      </ScrollView>
      <Modal
        transparent
        visible={selected !== null}
        animationType="fade"
        onRequestClose={closeAnalysis}
        onDismiss={() => focusTarget.current?.focus()}
      >
        <View style={st.overlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityRole="button"
            accessibilityLabel="키워드 분석 닫기"
            onPress={closeAnalysis}
          />
          <View
            onAccessibilityEscape={closeAnalysis}
            accessibilityViewIsModal
            style={[
              st.sheet,
              Platform.OS === "web" && popover
                ? {
                    position: "absolute",
                    width: Math.min(360, width - 32),
                    left: Math.min(
                      Math.max(16, popover.x),
                      Math.max(16, width - 376),
                    ),
                    top: Math.min(popover.y + 32, Math.max(16, height - 420)),
                    maxHeight: height - 32,
                  }
                : {},
            ]}
          >
            {selected && (
              <ScrollView contentContainerStyle={{ gap: 16 }}>
                <View
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
                  <Text style={st.category}>
                    {keywordCategories[selected.category]}
                  </Text>
                  <Button title="닫기" secondary onPress={closeAnalysis} />
                </View>
                <Text accessibilityRole="header" style={s.heading}>
                  {selected.keyword}
                </Text>
                {[
                  ["뜻", selected.definition],
                  ["기사 맥락", selected.context],
                  ["확인할 점", selected.watchPoint],
                ].map(([label, value]) => (
                  <View key={label} style={{ gap: 6 }}>
                    <Text style={s.label}>{label}</Text>
                    <Text selectable style={s.body}>
                      {value || "아직 설명이 제공되지 않았습니다."}
                    </Text>
                  </View>
                ))}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}
function KeywordText({
  keyword,
  show,
}: {
  keyword: Keyword;
  show: (
    keyword: Keyword,
    target?: React.ElementRef<typeof Text> | null,
  ) => void;
}) {
  const ref = useRef<React.ElementRef<typeof Text>>(null);
  return (
    <Text
      ref={ref}
      style={st.inlineKeyword}
      accessibilityRole="button"
      accessibilityLabel={`${keyword.keyword} 키워드 분석`}
      accessibilityHint="뜻과 기사 맥락, 확인할 점을 엽니다"
      onPress={() => show(keyword, ref.current)}
      onPointerEnter={(e) => {
        if (e.nativeEvent.pointerType !== "touch") show(keyword, ref.current);
      }}
    >
      {keyword.keyword}
    </Text>
  );
}
const st = StyleSheet.create({
  toolbar: {
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: c.line,
  },
  back: { minHeight: 48, justifyContent: "center", alignSelf: "flex-start" },
  article: { padding: 20, paddingTop: 20, paddingBottom: 28, gap: 16, width: "100%", maxWidth: 680, alignSelf: "center" },
  meta: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 12,
  },
  category: { fontSize: 12, lineHeight: 18, color: c.accent, fontWeight: "600" },
  source: { minHeight: 44, justifyContent: "center" },
  headline: { fontSize: 22, lineHeight: 31, color: c.ink, fontWeight: "700" },
  body: { fontSize: 15, lineHeight: 25, color: c.ink },
  photo: { width: "100%", aspectRatio: 1.6, borderRadius: 12 },
  photoMissing: {
    height: 120,
    backgroundColor: c.soft,
    justifyContent: "center",
    alignItems: "center",
  },
  credit: { fontSize: 12, color: c.muted },
  section: {
    gap: 12,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: c.line,
  },
  loading: { flexDirection: "row", gap: 12, paddingVertical: 12 },
  inlineKeyword: {
    color: c.accent,
    fontWeight: "700",
    textDecorationLine: "underline",
  },
  keywordList: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  keyword: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    minHeight: 48,
    borderRadius: 24,
    backgroundColor: c.selected,
    justifyContent: "center",
  },
  overlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.25)",
  },
  sheet: {
    backgroundColor: c.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    paddingBottom: 28,
    maxHeight: "75%",
    borderWidth: 1,
    borderColor: c.line,
  },
});
