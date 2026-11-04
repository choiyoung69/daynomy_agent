import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Text,
  View,
} from "react-native";
import { APIClient, ApiError, buildURL } from "../api";
import { Button, Chip, Empty, Field, Section, s } from "./kit";
import { theme as c } from "./theme";
type Source = { name: string; url: string };
type Item = {
  id: number;
  title?: string;
  content?: string;
  category?: string;
  status: string;
  publishedAt?: string | null;
  createdAt?: string;
  pagePath?: string | null;
};
type Form = {
  id?: number;
  title: string;
  content: string;
  category: string;
  sources: Source[];
  assetIds?: number[];
};
const categories = [
  ["STOCK", "주식"],
  ["ETF", "ETF"],
  ["REAL_ESTATE", "부동산"],
];
const statuses: Record<string, string> = {
  DRAFT: "초안",
  PUBLISHED: "발행됨",
  REJECTED: "거절됨",
  DELETED: "삭제됨",
  PENDING: "대기 중",
  RESOLVED: "처리 완료",
};
const text = (error: unknown) =>
  error instanceof Error ? error.message : "요청을 완료하지 못했어요.";
const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
async function saveNews(
  api: APIClient,
  form: Form,
  signal: AbortSignal,
): Promise<unknown> {
  const csrf = await api.request("/api/auth/csrf", {
    retryUnauthorized: false,
    signal,
  });
  if (
    !record(csrf) ||
    typeof csrf.headerName !== "string" ||
    !/^X-[!#$%&'*+.^_`|~0-9A-Za-z-]+$/i.test(csrf.headerName) ||
    typeof csrf.token !== "string" ||
    !csrf.token ||
    /[\r\n]/.test(csrf.token)
  )
    throw new Error("CSRF 응답을 확인하지 못했어요.");
  if (signal.aborted) throw new Error("요청이 취소되었습니다.");
  const boundary = `daynomy-news-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const data = {
    title: form.title.trim(),
    content: form.content.trim(),
    category: form.category,
    sources: form.sources.map((source) => ({
      name: source.name.trim(),
      url: source.url.trim(),
    })),
    ...(form.assetIds ? { assetIds: form.assetIds } : {}),
  };
  const body = `--${boundary}\r\nContent-Disposition: form-data; name="request"\r\nContent-Type: application/json\r\n\r\n${JSON.stringify(data)}\r\n--${boundary}--\r\n`;
  const headers = new Headers({
    "Content-Type": `multipart/form-data; boundary=${boundary}`,
    Accept: "application/json",
  });
  headers.set(csrf.headerName, csrf.token);
  const response = await fetch(
    buildURL(
      api.baseURL,
      form.id ? `/api/admin/news/${form.id}` : "/api/admin/news",
    ),
    {
      method: form.id ? "PUT" : "POST",
      credentials: "include",
      headers,
      body,
      signal,
    },
  );
  if (!response.ok) {
    let message: string | undefined, code: string | undefined;
    try {
      const value: unknown = await response.json();
      if (record(value)) {
        if (typeof value.message === "string") message = value.message;
        if (typeof value.code === "string") code = value.code;
      }
    } catch {}
    throw new ApiError(response.status, code, message);
  }
  return response.status === 204 ? null : response.json();
}
export function Admin({
  api,
  onClose,
}: {
  api: APIClient;
  onClose?: () => void;
}) {
  const [tab, setTab] = useState<"news" | "feedback">("news"),
    [page, setPage] = useState(1),
    [filter, setFilter] = useState("ALL"),
    [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [items, setItems] = useState<Item[]>([]),
    [hasNext, setHasNext] = useState(false),
    [loading, setLoading] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [tick, setTick] = useState(0),
    [form, setForm] = useState<Form | null>(null);
  const active = useRef(true),
    writing = useRef(false),
    mutation = useRef<AbortController | null>(null),
    sequence = useRef(0);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      mutation.current?.abort();
    };
  }, [api]);
  useEffect(() => {
    const seq = ++sequence.current;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setItems([]);
    api
      .call(tab === "news" ? "adminNews" : "adminFeedbacks", {
        query: {
          page,
          size: 15,
          ...(tab === "news" && filter !== "ALL" ? { status: filter } : {}),
          ...(tab === "news" && search ? { q: search } : {}),
        },
        signal: controller.signal,
      })
      .then((raw) => {
        if (
          !record(raw) ||
          !Array.isArray(raw.items) ||
          typeof raw.hasNext !== "boolean"
        )
          throw new Error("관리자 목록 응답 형식이 올바르지 않습니다.");
        if (active.current && seq === sequence.current) {
          setItems(raw.items as Item[]);
          setHasNext(raw.hasNext);
        }
      })
      .catch((e) => {
        if (
          active.current &&
          !controller.signal.aborted &&
          seq === sequence.current
        )
          setError(text(e));
      })
      .finally(() => {
        if (active.current && seq === sequence.current) setLoading(false);
      });
    return () => controller.abort();
  }, [api, tab, page, filter, search, tick]);
  const run = async (
    work: (signal: AbortSignal) => Promise<unknown>,
    success: string,
  ) => {
    if (writing.current) return;
    writing.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    const controller = new AbortController();
    mutation.current = controller;
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      await work(controller.signal);
      if (active.current && !controller.signal.aborted) {
        setMessage(success);
        setTick((value) => value + 1);
      }
    } catch (e) {
      if (active.current)
        setError(
          controller.signal.aborted
            ? "요청이 끝나지 않았어요. 결과를 새로 조회한 뒤 다시 시도해 주세요."
            : text(e),
        );
    } finally {
      clearTimeout(timer);
      writing.current = false;
      if (active.current) setBusy(false);
    }
  };
  const confirm = (
    title: string,
    detail: string,
    work: (signal: AbortSignal) => Promise<unknown>,
    success: string,
  ) =>
    Alert.alert(title, detail, [
      { text: "취소", style: "cancel" },
      {
        text: "확인",
        style: "destructive",
        onPress: () => void run(work, success),
      },
    ]);
  const edit = (item: Item) =>
    void run(async (signal) => {
      const raw = await api.call("adminNewsDetail", { id: item.id, signal });
      if (
        !record(raw) ||
        typeof raw.title !== "string" ||
        typeof raw.content !== "string" ||
        typeof raw.category !== "string" ||
        !Array.isArray(raw.sources)
      )
        throw new Error("뉴스 상세를 확인하지 못했어요.");
      if (!active.current) return;
      setForm({
        id: item.id,
        title: raw.title,
        content: raw.content,
        category: raw.category,
        sources: raw.sources.map((source) => ({
          name: String(source.name ?? ""),
          url: String(source.url ?? ""),
        })),
        ...(Array.isArray(raw.relatedAssets)
          ? { assetIds: raw.relatedAssets.map((asset) => asset.assetId) }
          : {}),
      });
    }, "뉴스를 불러왔습니다.");
  const changeSource = (index: number, key: keyof Source, value: string) =>
    setForm((previous) =>
      previous
        ? {
            ...previous,
            sources: previous.sources.map((source, i) =>
              i === index ? { ...source, [key]: value } : source,
            ),
          }
        : previous,
    );
  const submit = () => {
    if (!form) return;
    if (!form.title.trim() || !form.content.trim()) {
      setError("제목과 본문을 모두 입력해 주세요.");
      return;
    }
    if (
      !form.sources.length ||
      form.sources.some(
        (source) =>
          !source.name.trim() || !/^https?:\/\//i.test(source.url.trim()),
      )
    ) {
      setError("출처 이름과 올바른 웹 주소를 하나 이상 입력해 주세요.");
      return;
    }
    const snapshot = {
      ...form,
      sources: form.sources.map((source) => ({ ...source })),
    };
    void run(
      async (signal) => {
        await saveNews(api, snapshot, signal);
        if (active.current) setForm(null);
      },
      form.id ? "뉴스를 수정했습니다." : "뉴스 초안을 등록했습니다.",
    );
  };
  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: c.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View
        style={{
          padding: 20,
          borderBottomWidth: 1,
          borderColor: c.line,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Text accessibilityRole="header" style={s.heading}>
          {form ? (form.id ? "뉴스 수정" : "뉴스 초안 등록") : "관리자"}
        </Text>
        {form ? (
          <Button
            title="목록으로"
            secondary
            disabled={busy}
            onPress={() => {
              setForm(null);
              setError("");
            }}
          />
        ) : (
          onClose && <Button title="닫기" secondary onPress={onClose} />
        )}
      </View>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: 20, gap: 20, paddingBottom: 40 }}
      >
        {!!error && (
          <View
            accessibilityLiveRegion="assertive"
            style={{
              padding: 16,
              backgroundColor: "#FCECF0",
              borderRadius: 12,
            }}
          >
            <Text style={{ color: c.danger, lineHeight: 23 }}>{error}</Text>
          </View>
        )}
        {!!message && !error && (
          <Text accessibilityLiveRegion="polite" style={s.muted}>
            {message}
          </Text>
        )}
        {form ? (
          <>
            <Section
              title="뉴스 내용"
              detail="등록한 뉴스는 초안으로 저장됩니다. 발행은 목록에서 별도로 실행하세요."
            >
              <Field
                label="제목"
                value={form.title}
                onChangeText={(title) => setForm({ ...form, title })}
              />
              <Field
                label="본문"
                value={form.content}
                onChangeText={(content) => setForm({ ...form, content })}
                multiline
              />
              <Text style={s.label}>분류</Text>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                {categories.map(([category, label]) => (
                  <Chip
                    key={category}
                    title={label!}
                    selected={form.category === category}
                    onPress={() => setForm({ ...form, category: category! })}
                  />
                ))}
              </View>
              {!categories.some(([category]) => category === form.category) && (
                <Text style={s.caption}>기존 분류: {form.category}</Text>
              )}
            </Section>
            <Section
              title="출처"
              detail="뉴스의 근거를 확인할 수 있는 원문 출처를 입력하세요."
            >
              {form.sources.map((source, index) => (
                <View key={index} style={{ gap: 12 }}>
                  <Field
                    label={`출처 ${index + 1} 이름`}
                    value={source.name}
                    onChangeText={(value) => changeSource(index, "name", value)}
                  />
                  <Field
                    label={`출처 ${index + 1} 웹 주소`}
                    value={source.url}
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="url"
                    onChangeText={(value) => changeSource(index, "url", value)}
                  />
                  {form.sources.length > 1 && (
                    <Button
                      title={`출처 ${index + 1} 삭제`}
                      secondary
                      disabled={busy}
                      onPress={() =>
                        setForm({
                          ...form,
                          sources: form.sources.filter((_, i) => i !== index),
                        })
                      }
                    />
                  )}
                  <View style={s.divider} />
                </View>
              ))}
              <Button
                title="출처 추가"
                secondary
                disabled={busy}
                onPress={() =>
                  setForm({
                    ...form,
                    sources: [...form.sources, { name: "", url: "" }],
                  })
                }
              />
            </Section>
            <Text style={s.caption}>
              이미지 업로드와 연결 종목 편집은 이 화면에서 제공하지 않습니다.
            </Text>
            <Button
              title={
                busy ? "저장 중…" : form.id ? "수정 내용 저장" : "초안 등록"
              }
              disabled={busy}
              onPress={submit}
            />
          </>
        ) : (
          <>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Chip
                title="뉴스 관리"
                selected={tab === "news"}
                onPress={() => {
                  setTab("news");
                  setPage(1);
                }}
              />
              <Chip
                title="피드백 관리"
                selected={tab === "feedback"}
                onPress={() => {
                  setTab("feedback");
                  setPage(1);
                }}
              />
            </View>
            {tab === "news" && (
              <>
                <Button
                  title="+ 뉴스 초안 등록"
                  disabled={busy}
                  onPress={() => {
                    setError("");
                    setMessage("");
                    setForm({
                      title: "",
                      content: "",
                      category: "STOCK",
                      sources: [{ name: "", url: "" }],
                      assetIds: [],
                    });
                  }}
                />
                <Field
                  label="뉴스 제목·본문 검색"
                  value={query}
                  onChangeText={setQuery}
                  returnKeyType="search"
                  onSubmitEditing={() => {
                    setPage(1);
                    setSearch(query.trim());
                  }}
                />
                <Button
                  title="검색"
                  secondary
                  disabled={busy}
                  onPress={() => {
                    setPage(1);
                    setSearch(query.trim());
                  }}
                />
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={{ gap: 8 }}
                >
                  {["ALL", "DRAFT", "PUBLISHED", "REJECTED"].map((status) => (
                    <Chip
                      key={status}
                      title={status === "ALL" ? "전체" : statuses[status]!}
                      selected={filter === status}
                      onPress={() => {
                        setFilter(status);
                        setPage(1);
                      }}
                    />
                  ))}
                </ScrollView>
              </>
            )}
            {loading ? (
              <ActivityIndicator color={c.accent} />
            ) : items.length ? (
              items.map((item) =>
                tab === "news" ? (
                  <Section
                    key={item.id}
                    title={item.title ?? "뉴스"}
                    detail={`${statuses[item.status] ?? item.status} · ${item.publishedAt?.slice(0, 10) ?? "미발행"}`}
                  >
                    <View
                      style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}
                    >
                      <Button
                        title="수정"
                        secondary
                        disabled={busy || item.status === "DELETED"}
                        onPress={() => edit(item)}
                      />
                      {item.status === "DRAFT" && (
                        <>
                          <Button
                            title="발행"
                            disabled={busy}
                            onPress={() =>
                              confirm(
                                "뉴스를 발행할까요?",
                                "공개 뉴스 목록에 표시됩니다.",
                                (signal) =>
                                  api.call("adminPublishNews", {
                                    id: item.id,
                                    signal,
                                  }),
                                "뉴스를 발행했습니다.",
                              )
                            }
                          />
                          <Button
                            title="거절"
                            secondary
                            disabled={busy}
                            onPress={() =>
                              confirm(
                                "이 초안을 거절할까요?",
                                "초안이 거절 상태로 변경됩니다.",
                                (signal) =>
                                  api.call("adminRejectNews", {
                                    id: item.id,
                                    signal,
                                  }),
                                "초안을 거절했습니다.",
                              )
                            }
                          />
                        </>
                      )}
                      {item.status !== "DELETED" && (
                        <Button
                          title="삭제"
                          danger
                          disabled={busy}
                          onPress={() =>
                            confirm(
                              "뉴스를 삭제할까요?",
                              "삭제한 뉴스는 공개 목록에서 사라집니다.",
                              (signal) =>
                                api.call("adminDeleteNews", {
                                  id: item.id,
                                  signal,
                                }),
                              "뉴스를 삭제했습니다.",
                            )
                          }
                        />
                      )}
                    </View>
                  </Section>
                ) : (
                  <Section
                    key={item.id}
                    title={`피드백 #${item.id}`}
                    detail={`${statuses[item.status] ?? item.status} · ${item.createdAt?.slice(0, 10) ?? ""}`}
                  >
                    <Text selectable style={s.body}>
                      {item.content}
                    </Text>
                    {!!item.pagePath && (
                      <Text style={s.caption}>접수 화면: {item.pagePath}</Text>
                    )}
                    <Button
                      title={
                        item.status === "PENDING"
                          ? "처리 완료로 변경"
                          : "대기 중으로 변경"
                      }
                      secondary
                      disabled={busy}
                      onPress={() =>
                        void run(
                          (signal) =>
                            api.call("adminUpdateFeedback", {
                              id: item.id,
                              body: {
                                status:
                                  item.status === "PENDING"
                                    ? "RESOLVED"
                                    : "PENDING",
                              },
                              signal,
                            }),
                          "피드백 상태를 변경했습니다.",
                        )
                      }
                    />
                    <Button
                      title="피드백 삭제"
                      danger
                      disabled={busy}
                      onPress={() =>
                        confirm(
                          "피드백을 삭제할까요?",
                          "삭제한 피드백은 복구할 수 없습니다.",
                          (signal) =>
                            api.call("adminDeleteFeedback", {
                              id: item.id,
                              signal,
                            }),
                          "피드백을 삭제했습니다.",
                        )
                      }
                    />
                  </Section>
                ),
              )
            ) : (
              !error && (
                <Empty
                  title={
                    tab === "news"
                      ? "조건에 맞는 뉴스가 없어요"
                      : "접수된 피드백이 없어요"
                  }
                  detail="목록을 새로 불러오거나 다른 조건을 선택해 주세요."
                />
              )
            )}
            <View style={s.row}>
              <Button
                title="이전"
                secondary
                disabled={loading || page === 1}
                onPress={() => setPage((value) => value - 1)}
              />
              <Text style={s.muted}>{page} 페이지</Text>
              <Button
                title="다음"
                secondary
                disabled={loading || !hasNext}
                onPress={() => setPage((value) => value + 1)}
              />
            </View>
            <Button
              title="목록 새로고침"
              secondary
              disabled={loading || busy}
              onPress={() => setTick((value) => value + 1)}
            />
            <Text style={s.caption}>
              인물·게시 후보와 이미지 작업은 조회 화면에서 확인할 수 있습니다.
            </Text>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
