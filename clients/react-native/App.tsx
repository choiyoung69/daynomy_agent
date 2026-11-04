import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ActivityIndicator,
  Alert,
  BackHandler,
  FlatList,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as WebBrowser from "expo-web-browser";
import {
  APIClient,
  StockSelection,
  replayLedger,
  validateTrade,
} from "./src/api";
import type { Stock, Trade } from "./src/api";
import { Button, Chip, Empty, Field, Section, s } from "./src/ui/kit";
import { theme as c } from "./src/ui/theme";
import { Admin } from "./src/ui/Admin";
import { todayInSeoul } from "./src/storage";

const localDate = todayInSeoul;
const errorText = (e: unknown) =>
  e instanceof Error
    ? e.message
    : "요청을 완료하지 못했습니다. 다시 확인해 주세요.";
const money = (n: unknown) =>
  typeof n === "number"
    ? n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })
    : typeof n === "string"
      ? n
      : "—";
const array = (v: any): any[] =>
  Array.isArray(v)
    ? v
    : Array.isArray(v?.items)
      ? v.items
      : Array.isArray(v?.content)
        ? v.content
        : [];
const STORAGE = "daynomy.rn.guest-trades.v1";
const DEFAULT_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  (Platform.OS === "android"
    ? "http://10.0.2.2:18081"
    : "http://127.0.0.1:18081");
type Tab = "portfolio" | "news" | "explore" | "calendar" | "more";
type Panel = {
  title: string;
  path?: string;
  name?: string;
  id?: number;
  query?: Record<string, string>;
  data?: unknown;
  admin?: boolean;
};
const tabs: {
  key: Tab;
  label: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
}[] = [
  { key: "portfolio", label: "내 자산", icon: "pie-chart-outline" },
  { key: "news", label: "뉴스", icon: "newspaper-outline" },
  { key: "explore", label: "탐색", icon: "search-outline" },
  { key: "calendar", label: "캘린더", icon: "calendar-outline" },
  { key: "more", label: "더보기", icon: "ellipsis-horizontal-outline" },
];

export default function App() {
  return (
    <SafeAreaProvider>
      <Main />
    </SafeAreaProvider>
  );
}
function Main() {
  const [tab, setTab] = useState<Tab>("portfolio"),
    [baseURL, setBaseURL] = useState(DEFAULT_URL),
    [profile, setProfile] = useState<any>(null),
    [trades, setTrades] = useState<Trade[]>([]),
    [hydrated, setHydrated] = useState(false),
    [storageError, setStorageError] = useState(""),
    [editor, setEditor] = useState<Trade | null | undefined>(undefined),
    [panel, setPanel] = useState<Panel | null>(null),
    [revision, setRevision] = useState(0);
  const api = useMemo(() => new APIClient({ baseURL }), [baseURL]);
  const apiRef = useRef(api);
  apiRef.current = api;
  const { width } = useWindowDimensions();
  const persistence = useRef(false);
  useEffect(() => {
    let live = true;
    AsyncStorage.getItem(STORAGE)
      .then((raw) => {
        if (raw) {
          const parsed: unknown = JSON.parse(raw);
          if (!Array.isArray(parsed))
            throw new Error("저장된 거래 형식이 올바르지 않습니다.");
          parsed.forEach((t) => validateTrade(t, localDate()));
          replayLedger(parsed);
          if (live) setTrades(parsed);
        }
      })
      .catch((e) => {
        if (live) setStorageError(errorText(e));
      })
      .finally(() => {
        if (live) setHydrated(true);
      });
    return () => {
      live = false;
    };
  }, []);
  const refreshProfile = useCallback(async () => {
    try {
      const next = await api.call("profile");
      if (apiRef.current === api) setProfile(next);
    } catch {
      if (apiRef.current === api) setProfile(null);
    }
  }, [api]);
  useEffect(() => {
    setProfile(null);
    void refreshProfile();
    return () => api.invalidateSession();
  }, [api, refreshProfile]);
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (editor !== undefined) {
        setEditor(undefined);
        return true;
      }
      if (panel) {
        setPanel(null);
        return true;
      }
      if (tab !== "portfolio") {
        setTab("portfolio");
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [editor, panel, tab]);
  const saveTrades = async (next: Trade[]) => {
    if (persistence.current) throw new Error("이전 저장을 기다려 주세요.");
    replayLedger(next);
    persistence.current = true;
    try {
      await AsyncStorage.setItem(STORAGE, JSON.stringify(next));
      setTrades(next);
      setRevision((n) => n + 1);
    } finally {
      persistence.current = false;
    }
  };
  const holdings = useMemo(() => {
    try {
      return replayLedger(trades).holdings.map((h) => ({
        ...trades.find((t) => t.stock.assetId === h.assetId)!.stock,
        ...h,
      }));
    } catch {
      return [];
    }
  }, [trades]);
  const confirmDelete = (trade: Trade) =>
    Alert.alert(
      "거래를 삭제할까요?",
      `${trade.stock.name} 거래가 원장에서 삭제됩니다.`,
      [
        { text: "취소", style: "cancel" },
        {
          text: "삭제",
          style: "destructive",
          onPress: () => {
            void saveTrades(trades.filter((t) => t.id !== trade.id)).catch(
              (e) => Alert.alert("삭제할 수 없습니다", errorText(e)),
            );
          },
        },
      ],
    );
  const onSave = async (trade: Trade) => {
    validateTrade(trade, localDate());
    if (profile) {
      const editing = !!editor?.unitPrice;
      const body = {
        ...(editing ? {} : { assetId: trade.stock.assetId, type: trade.type }),
        tradeDate: trade.date,
        quantity: trade.quantity,
        unitPrice: trade.unitPrice,
        fee: trade.fee,
        tax: trade.tax,
        exchangeRate: trade.exchangeRate ?? null,
      };
      await api.call(editing ? "updateTrade" : "createTrade", {
        id: editing ? editor?.id : undefined,
        body,
      });
      setRevision((n) => n + 1);
    } else {
      await saveTrades([...trades.filter((t) => t.id !== trade.id), trade]);
    }
    setEditor(undefined);
  };
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <StatusBar style="dark" />
      <View
        style={[
          styles.app,
          width > 720 && { maxWidth: 920, alignSelf: "center", width: "100%" },
        ]}
      >
        <View style={styles.brand}>
          <Text style={styles.logo}>
            DAYNOMY<Text style={{ color: c.accent }}>•</Text>
          </Text>
          <View style={styles.mode}>
            <View style={styles.dot} />
            <Text style={s.caption}>
              {profile ? "회원 포트폴리오" : "게스트 포트폴리오"}
            </Text>
          </View>
        </View>
        <View style={{ flex: 1 }}>
          {tab === "portfolio" && (
            <Portfolio
              api={api}
              profile={profile}
              holdings={holdings}
              trades={trades}
              hydrated={hydrated}
              storageError={storageError}
              revision={revision}
              onAdd={() => setEditor(null)}
              onEdit={setEditor}
              onDelete={confirmDelete}
              openPanel={setPanel}
            />
          )}
          {tab === "news" && <News api={api} openPanel={setPanel} />}
          {tab === "explore" && (
            <Explore
              api={api}
              openPanel={setPanel}
              onTrade={(stock: Stock) =>
                setEditor({
                  id: Date.now(),
                  stock,
                  type: "BUY",
                  date: localDate(),
                  quantity: 1,
                  unitPrice: "",
                  fee: "0",
                  tax: "0",
                })
              }
            />
          )}
          {tab === "calendar" && (
            <Calendar api={api} member={!!profile} holdings={holdings} />
          )}
          {tab === "more" && (
            <More
              api={api}
              baseURL={baseURL}
              setBaseURL={setBaseURL}
              profile={profile}
              refreshProfile={refreshProfile}
              openPanel={setPanel}
            />
          )}
        </View>
        <View style={styles.nav}>
          {tabs.map((t) => (
            <Pressable
              key={t.key}
              accessibilityRole="tab"
              accessibilityLabel={t.label}
              accessibilityState={{ selected: tab === t.key }}
              onPress={() => setTab(t.key)}
              style={({ pressed }) => [
                styles.navItem,
                pressed && { opacity: 0.6 },
              ]}
            >
              <Ionicons
                name={t.icon}
                size={23}
                color={tab === t.key ? c.accent : c.muted}
                importantForAccessibility="no"
              />
              <Text
                style={{
                  fontSize: 11,
                  fontWeight: tab === t.key ? "700" : "500",
                  color: tab === t.key ? c.accent : c.muted,
                }}
              >
                {t.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <Modal
          visible={editor !== undefined}
          animationType="slide"
          onRequestClose={() => setEditor(undefined)}
        >
          <SafeAreaView style={styles.safe}>
            <TradeEditor
              api={api}
              initial={editor ?? null}
              onClose={() => setEditor(undefined)}
              onSave={onSave}
            />
          </SafeAreaView>
        </Modal>
        <Modal
          visible={!!panel}
          animationType="slide"
          onRequestClose={() => setPanel(null)}
        >
          <SafeAreaView style={styles.safe}>
            {panel &&
              (panel.admin ? (
                <Admin api={api} onClose={() => setPanel(null)} />
              ) : (
                <Detail api={api} panel={panel} close={() => setPanel(null)} />
              ))}
          </SafeAreaView>
        </Modal>
      </View>
    </SafeAreaView>
  );
}
function Page({
  title,
  eyebrow,
  children,
  refreshing,
  onRefresh,
}: {
  title: string;
  eyebrow: string;
  children: React.ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      refreshControl={
        onRefresh ? (
          <RefreshControl
            refreshing={!!refreshing}
            onRefresh={onRefresh}
            tintColor={c.accent}
          />
        ) : undefined
      }
    >
      <View style={{ gap: 8, marginBottom: 4 }}>
        <Text style={s.badge}>{eyebrow}</Text>
        <Text accessibilityRole="header" style={styles.pageTitle}>
          {title}
        </Text>
      </View>
      {children}
    </ScrollView>
  );
}
function useLoad(load: () => Promise<unknown>, deps: React.DependencyList) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [tick, setTick] = useState(0);
  const seq = useRef(0);
  useEffect(() => {
    const id = ++seq.current;
    setLoading(true);
    setError("");
    setData(null);
    load()
      .then((v) => {
        if (seq.current === id) setData(v);
      })
      .catch((e) => {
        if (seq.current === id) setError(errorText(e));
      })
      .finally(() => {
        if (seq.current === id) setLoading(false);
      });
    return () => {
      seq.current++;
    };
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((v) => v + 1) };
}
function State({
  loading,
  error,
  retry,
}: {
  loading: boolean;
  error: string;
  retry: () => void;
}) {
  if (loading)
    return <ActivityIndicator color={c.accent} style={{ padding: 20 }} />;
  if (error)
    return (
      <View accessibilityLiveRegion="polite" style={{ gap: 12 }}>
        <Text style={{ color: c.danger, lineHeight: 22 }}>{error}</Text>
        <Button title="다시 시도" secondary onPress={retry} />
      </View>
    );
  return null;
}
function Portfolio({
  api,
  profile,
  holdings,
  trades,
  hydrated,
  storageError,
  revision,
  onAdd,
  onEdit,
  onDelete,
  openPanel,
}: any) {
  const [view, setView] = useState("보유 종목");
  const result = useLoad(async () => {
    const saved = profile ? await api.portfolio() : { holdings };
    const positions = saved.holdings ?? [];
    if (!positions.length)
      return { ...saved, totalEvaluationAmount: 0, totalProfitLoss: 0 };
    const calculation = await api.calculate(
      positions.map((h: any) => ({
        assetId: h.assetId,
        quantity: h.quantity,
        averagePurchasePrice: h.averagePurchasePrice,
      })),
    );
    return { ...saved, ...calculation };
  }, [api, profile, holdings, revision]);
  const memberTrades = useLoad(
    () =>
      profile
        ? api.call("histories", {
            query: { from: "2000-01-01", to: localDate() },
          })
        : Promise.resolve([]),
    [api, profile, revision],
  );
  const data = result.data;
  const currentHoldings = profile ? (data?.holdings ?? []) : holdings;
  return (
    <Page
      title="오늘의 자산을, 한눈에."
      eyebrow="MY PORTFOLIO"
      refreshing={result.loading}
      onRefresh={result.reload}
    >
      {!profile && (
        <Text style={s.muted}>
          로그인 없이 시작하세요. 거래 기록은 이 기기에 저장됩니다.
        </Text>
      )}
      <View style={styles.balance}>
        <Text style={{ color: "#D8D3FF", fontSize: 14 }}>총 평가금액</Text>
        <Text style={styles.balanceValue}>
          {data
            ? `${money(data.totalEvaluationAmount ?? data.calculation?.totalEvaluationAmount)} 원`
            : "—"}
        </Text>
        <View
          style={{ height: 1, backgroundColor: "#7669E8", marginVertical: 4 }}
        />
        <View style={s.row}>
          <Text style={{ color: "#EBE8FF" }}>투자 손익</Text>
          <Text style={{ color: "#FFF", fontWeight: "700" }}>
            {data
              ? `${money(data.totalProfitLoss ?? data.calculation?.totalProfitLoss)} 원`
              : "가격 조회 후 표시"}
          </Text>
        </View>
      </View>
      <View style={s.row}>
        <Button
          title="+ 거래 기록"
          onPress={onAdd}
          disabled={!hydrated || !!storageError}
        />
        {profile && (
          <Button
            title="포트폴리오 분석"
            secondary
            onPress={() =>
              openPanel({ title: "포트폴리오 분석", name: "analysis" })
            }
          />
        )}
      </View>
      {!!storageError && (
        <Text style={{ color: c.danger }}>
          {storageError} 기존 저장 내용을 보존하고 있습니다.
        </Text>
      )}
      <State {...result} retry={result.reload} />
      {profile && <State {...memberTrades} retry={memberTrades.reload} />}
      <View style={{ flexDirection: "row", gap: 8 }}>
        {["보유 종목", "거래 내역"].map((t) => (
          <Chip
            key={t}
            title={t}
            selected={view === t}
            onPress={() => setView(t)}
          />
        ))}
      </View>
      <Section
        title={view}
        detail={
          view === "보유 종목"
            ? `${currentHoldings.length}개 종목 · 최근 저장 종가 기준`
            : "날짜 순으로 거래 기록을 확인하세요."
        }
      >
        {!hydrated ? (
          <ActivityIndicator />
        ) : view === "보유 종목" ? (
          currentHoldings.length ? (
            currentHoldings.map((h: any) => (
              <View key={h.assetId} style={styles.holding}>
                <View style={styles.stockMark}>
                  <Text style={{ color: c.accent, fontWeight: "800" }}>
                    {String(h.name ?? h.assetCode ?? "S").slice(0, 1)}
                  </Text>
                </View>
                <View style={{ flex: 1, gap: 5 }}>
                  <Text style={s.title}>{h.name ?? h.assetCode}</Text>
                  <Text style={s.caption}>
                    {h.quantity}주 · {h.market}
                  </Text>
                </View>
                <View style={{ alignItems: "flex-end", gap: 5 }}>
                  <Text style={s.title}>
                    {money(h.evaluationAmount ?? h.averagePurchasePrice)}
                  </Text>
                  <Text style={s.caption}>
                    {h.evaluationAmount != null ? "평가금액" : "평균 매입가"}
                  </Text>
                </View>
              </View>
            ))
          ) : (
            <Empty
              title="첫 번째 투자를 기록해 보세요"
              detail="종목을 검색하고 매수 내역을 추가하면 자산 현황을 확인할 수 있어요."
            />
          )
        ) : (profile ? array(memberTrades.data) : trades).length ? (
          (profile ? array(memberTrades.data) : trades).map((t: any) => (
            <View key={t.id ?? t.historyId} style={{ gap: 12 }}>
              <View style={s.row}>
                <View style={{ gap: 4 }}>
                  <Text style={s.title}>
                    {t.stock?.name ?? t.name} ·{" "}
                    {t.type ?? t.changeType ?? t.transactionType}
                  </Text>
                  <Text style={s.muted}>
                    {t.date ?? t.effectiveDate ?? t.tradeDate ?? t.tradedOn} ·{" "}
                    {t.transactionQuantity ?? t.quantity}주 ×{" "}
                    {money(t.unitPrice)}
                  </Text>
                </View>
              </View>
              {!profile ? (
                <View style={{ flexDirection: "row", gap: 8 }}>
                  <Button title="수정" secondary onPress={() => onEdit(t)} />
                  <Button title="삭제" secondary onPress={() => onDelete(t)} />
                </View>
              ) : (
                ["BUY", "SELL"].includes(t.changeType) && (
                  <View style={{ flexDirection: "row", gap: 8 }}>
                    {currentHoldings.some(
                      (h: any) => h.assetId === t.assetId,
                    ) && (
                      <Button
                        title="수정"
                        secondary
                        onPress={() =>
                          onEdit({
                            id: t.historyId,
                            stock: currentHoldings.find(
                              (h: any) => h.assetId === t.assetId,
                            ),
                            type: t.changeType,
                            date: t.effectiveDate,
                            quantity: t.transactionQuantity,
                            unitPrice: String(t.unitPrice),
                            fee: String(t.fee ?? 0),
                            tax: String(t.tax ?? 0),
                            exchangeRate: t.exchangeRate
                              ? String(t.exchangeRate)
                              : undefined,
                          })
                        }
                      />
                    )}
                    <Button
                      title="삭제"
                      secondary
                      onPress={() =>
                        Alert.alert("거래 삭제", "이 거래를 삭제할까요?", [
                          { text: "취소", style: "cancel" },
                          {
                            text: "삭제",
                            style: "destructive",
                            onPress: () => {
                              api
                                .call("deleteTrade", { id: t.historyId })
                                .then(() => {
                                  memberTrades.reload();
                                  result.reload();
                                })
                                .catch((e: any) =>
                                  Alert.alert("삭제 실패", errorText(e)),
                                );
                            },
                          },
                        ])
                      }
                    />
                  </View>
                )
              )}
              <View style={s.divider} />
            </View>
          ))
        ) : (
          <Empty
            title="아직 기록된 거래가 없어요"
            detail="매수와 매도를 기록하면 내 투자 흐름이 쌓여요."
          />
        )}
      </Section>
      <Section title="투자 인사이트">
        <Button
          title="자산 추이 확인"
          secondary
          onPress={() =>
            openPanel({
              title: "자산 추이",
              name: profile ? "performance" : undefined,
              query: profile
                ? { from: `${new Date().getFullYear()}-01-01`, to: localDate() }
                : undefined,
              data: profile
                ? undefined
                : {
                    안내: "게스트의 자산 추이는 거래 기록과 종가 조회를 바탕으로 별도 지원 예정입니다.",
                  },
            })
          }
        />
        {!profile && holdings.length > 0 && (
          <GuestAnalysis api={api} holdings={data?.holdings ?? []} />
        )}
      </Section>
    </Page>
  );
}
function GuestAnalysis({ api, holdings }: any) {
  const [busy, setBusy] = useState(false),
    [data, setData] = useState<any>(null),
    [error, setError] = useState("");
  return (
    <View style={{ gap: 12 }}>
      <Button
        title="내 보유 종목 분석하기"
        secondary
        disabled={busy}
        onPress={() => {
          setBusy(true);
          setError("");
          api
            .analysis(
              false,
              holdings
                .filter(
                  (h: any) => typeof h.weight === "number" && h.weight > 0,
                )
                .map((h: any, i: number, all: any[]) => ({
                  assetName: h.name,
                  weight:
                    i === 0
                      ? Math.round(
                          (h.weight +
                            100 -
                            all.reduce(
                              (sum: number, v: any) => sum + v.weight,
                              0,
                            )) *
                            100,
                        ) / 100
                      : h.weight,
                })),
            )
            .then(setData)
            .catch((e: any) => setError(errorText(e)))
            .finally(() => setBusy(false));
        }}
      />
      {busy && <ActivityIndicator />}
      {!!error && <Text style={{ color: c.danger }}>{error}</Text>}
      {data && <DataView value={data} />}
    </View>
  );
}
function News({ api, openPanel }: any) {
  const [category, setCategory] = useState("ALL"),
    [page, setPage] = useState(1);
  const result = useLoad(
    () =>
      api.news({ page, size: 20, ...(category === "ALL" ? {} : { category }) }),
    [api, category, page],
  );
  const items = result.data?.items ?? [];
  return (
    <Page
      title="세상을 읽는 투자 습관."
      eyebrow="DAILY BRIEFING"
      refreshing={result.loading}
      onRefresh={result.reload}
    >
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ gap: 8 }}
      >
        {[
          ["ALL", "전체"],
          ["STOCK", "주식"],
          ["ETF", "ETF"],
          ["REAL_ESTATE", "부동산"],
        ].map(([key, label]) => (
          <Chip
            key={key}
            title={label!}
            selected={category === key}
            onPress={() => {
              setCategory(key!);
              setPage(1);
            }}
          />
        ))}
      </ScrollView>
      <State {...result} retry={result.reload} />
      {items.length
        ? items.map((n: any) => (
            <Pressable
              key={n.id ?? n.newsId}
              accessibilityRole="button"
              onPress={() =>
                openPanel({
                  title: "뉴스",
                  name: "newsDetail",
                  id: n.id ?? n.newsId,
                })
              }
              style={({ pressed }) => [
                styles.newsCard,
                pressed && { opacity: 0.7 },
              ]}
            >
              <Text style={s.badge}>{n.category ?? "DAYNOMY NEWS"}</Text>
              <Text
                style={{
                  fontSize: 20,
                  lineHeight: 29,
                  fontWeight: "700",
                  color: c.ink,
                }}
              >
                {n.title}
              </Text>
              {!!(n.summary ?? n.description) && (
                <Text numberOfLines={3} style={s.muted}>
                  {n.summary ?? n.description}
                </Text>
              )}
              <View style={s.row}>
                <Text style={s.caption}>
                  {n.publishedAt?.slice(0, 10) ?? n.createdAt?.slice(0, 10)}
                </Text>
                <Ionicons name="arrow-forward" size={20} color={c.accent} />
              </View>
            </Pressable>
          ))
        : !result.loading &&
          !result.error && (
            <Empty
              title="새 소식을 기다리고 있어요"
              detail="다른 카테고리를 선택하거나 잠시 뒤 다시 확인해 주세요."
            />
          )}
      <View style={s.row}>
        <Button
          title="이전"
          secondary
          disabled={page === 1}
          onPress={() => setPage((p) => p - 1)}
        />
        <Text style={s.muted}>{page} 페이지</Text>
        <Button
          title="다음"
          secondary
          disabled={!result.data?.hasNext}
          onPress={() => setPage((p) => p + 1)}
        />
      </View>
    </Page>
  );
}
function Explore({ api, openPanel, onTrade }: any) {
  const [q, setQ] = useState(""),
    [query, setQuery] = useState(""),
    [country, setCountry] = useState<"KR" | "US">("KR"),
    [kind, setKind] = useState("종목"),
    [category, setCategory] = useState("ALL");
  const result = useLoad(
    () =>
      !query
        ? Promise.resolve([])
        : kind === "종목"
          ? api.searchStocks(query, country)
          : api.call(kind === "뉴스" ? "newsSearch" : "contentSearch", {
              query: { q: query, page: 1, size: 20 },
            }),
    [api, query, country, kind],
  );
  const values = array(result.data).filter(
    (v: any) => category === "ALL" || v.category === category,
  );
  return (
    <Page title="나의 다음 관심사를 찾아요." eyebrow="DISCOVER">
      <View style={{ gap: 12 }}>
        <Field
          label="종목·뉴스·콘텐츠 검색"
          placeholder="삼성전자, AAPL, 금리…"
          value={q}
          onChangeText={setQ}
          returnKeyType="search"
          onSubmitEditing={() => setQuery(q.trim())}
        />
        <Button
          title="검색"
          onPress={() => setQuery(q.trim())}
          disabled={!q.trim()}
        />
      </View>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {["종목", "뉴스", "콘텐츠"].map((t) => (
          <Chip
            key={t}
            title={t}
            selected={kind === t}
            onPress={() => setKind(t)}
          />
        ))}
      </View>
      {kind === "종목" && (
        <>
          <View style={{ flexDirection: "row", gap: 8 }}>
            {(["KR", "US"] as const).map((t) => (
              <Chip
                key={t}
                title={t === "KR" ? "국내" : "미국"}
                selected={country === t}
                onPress={() => setCountry(t)}
              />
            ))}
          </View>
          <View style={{ flexDirection: "row", gap: 8 }}>
            {[
              ["ALL", "전체"],
              ["STOCK", "주식"],
              ["ETF", "ETF"],
            ].map(([k, t]) => (
              <Chip
                key={k}
                title={t!}
                selected={category === k}
                onPress={() => setCategory(k!)}
              />
            ))}
          </View>
        </>
      )}
      <State {...result} retry={result.reload} />
      <Section title={query ? `“${query}” 검색 결과` : "관심을 자산으로"}>
        {!query ? (
          <Empty
            title="어떤 투자가 궁금한가요?"
            detail="종목 이름이나 코드를 검색해 보세요. 국내 주식과 미국 주식을 함께 살펴볼 수 있어요."
          />
        ) : !values.length && !result.loading ? (
          <Empty
            title="검색 결과가 없어요"
            detail="다른 이름이나 종목 코드로 검색해 주세요."
          />
        ) : (
          values.map((v: any, i: number) => (
            <View key={v.assetId ?? v.id ?? i} style={{ gap: 12 }}>
              <Pressable
                accessibilityRole="button"
                onPress={() =>
                  kind === "종목"
                    ? onTrade(v)
                    : openPanel({
                        title: v.title ?? "콘텐츠",
                        ...(kind === "뉴스"
                          ? { name: "newsDetail", id: v.id ?? v.newsId }
                          : { data: v }),
                      })
                }
              >
                <View style={s.row}>
                  <View style={{ flex: 1, gap: 6 }}>
                    <Text style={s.title}>{v.name ?? v.title}</Text>
                    <Text style={s.caption}>
                      {v.assetCode ?? v.summary} {v.market} {v.category}
                    </Text>
                  </View>
                  <Ionicons name="arrow-forward" size={20} color={c.accent} />
                </View>
              </Pressable>
              {kind === "종목" && (
                <Button
                  title="관련 콘텐츠"
                  secondary
                  onPress={() =>
                    openPanel({
                      title: `${v.name} 관련 자료`,
                      name: "assetContents",
                      id: v.assetId,
                    })
                  }
                />
              )}
              <View style={s.divider} />
            </View>
          ))
        )}
      </Section>
      <Button
        title="투자 인물 살펴보기"
        secondary
        onPress={() => openPanel({ title: "투자 인물", name: "people" })}
      />
    </Page>
  );
}
function Calendar({ api, member, holdings }: any) {
  const [now, setNow] = useState(new Date()),
    [scope, setScope] = useState<"ALL" | "PORTFOLIO">("ALL");
  const year = now.getFullYear(),
    month = now.getMonth() + 1;
  const result = useLoad(
    () =>
      api.calendar(
        year,
        month,
        scope,
        member,
        holdings.map((h: any) => ({
          assetId: h.assetId,
          quantity: h.quantity,
          averagePurchasePrice: h.averagePurchasePrice,
        })),
      ),
    [api, member, holdings, year, month, scope],
  );
  const events = result.data?.events ?? [];
  return (
    <Page title="미리 살피는 투자 일정." eyebrow="INVESTMENT CALENDAR">
      <Section title={`${year}년 ${month}월`}>
        <View style={s.row}>
          <Button
            title="이전 달"
            secondary
            onPress={() => setNow(new Date(year, month - 2, 1))}
          />
          <Button
            title="이번 달"
            secondary
            onPress={() => setNow(new Date())}
          />
          <Button
            title="다음 달"
            secondary
            onPress={() => setNow(new Date(year, month, 1))}
          />
        </View>
        <View style={{ flexDirection: "row", gap: 8 }}>
          {(["ALL", "PORTFOLIO"] as const).map((k) => (
            <Chip
              key={k}
              title={k === "ALL" ? "전체 일정" : "내 종목"}
              selected={scope === k}
              onPress={() => setScope(k)}
            />
          ))}
        </View>
        <State {...result} retry={result.reload} />
        {events.length
          ? events.map((e: any) => (
              <View
                key={e.id}
                style={{
                  gap: 10,
                  paddingVertical: 12,
                  borderBottomWidth: 1,
                  borderColor: c.line,
                }}
              >
                <Text style={s.badge}>
                  {e.announcedAt?.slice(0, 10)} ·{" "}
                  {e.upcoming ? `D-${e.daysUntil}` : "발표 완료"}
                </Text>
                <Text style={s.title}>{e.title}</Text>
                <Text style={s.muted}>
                  이전 {e.value?.previousValue ?? "—"} → 발표{" "}
                  {e.value?.actualValue ?? "—"} {e.value?.unit}
                </Text>
                {!!e.source?.url && (
                  <Button
                    title={`${e.source.name ?? "출처"} 확인`}
                    secondary
                    onPress={() => openExternal(e.source.url)}
                  />
                )}
              </View>
            ))
          : !result.loading &&
            !result.error && (
              <Empty
                title="등록된 일정이 없어요"
                detail="다른 달이나 전체 일정을 확인해 보세요."
              />
            )}
      </Section>
    </Page>
  );
}
function TradeEditor({
  api,
  initial,
  onSave,
  onClose,
}: {
  api: APIClient;
  initial: Trade | null;
  onSave: (t: Trade) => Promise<void>;
  onClose: () => void;
}) {
  const model = useRef(new StockSelection()).current;
  const [stock, setStock] = useState<Stock | null>(initial?.stock ?? null),
    [q, setQ] = useState(""),
    [country, setCountry] = useState<"KR" | "US">("KR"),
    [stocks, setStocks] = useState<Stock[]>([]),
    [price, setPrice] = useState(initial?.unitPrice ?? ""),
    [date, setDate] = useState(initial?.date ?? localDate()),
    [quantity, setQuantity] = useState(String(initial?.quantity ?? 1)),
    [fee, setFee] = useState(initial?.fee ?? "0"),
    [tax, setTax] = useState(initial?.tax ?? "0"),
    [fx, setFx] = useState(initial?.exchangeRate ?? ""),
    [type, setType] = useState<"BUY" | "SELL">(initial?.type ?? "BUY"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [searching, setSearching] = useState(false),
    [priceDate, setPriceDate] = useState("");
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    if (initial?.stock && !initial.unitPrice) void select(initial.stock);
    return () => {
      abort.current?.abort();
      model.beginSearch();
      if (stock) model.select(stock);
    };
  }, []);
  const search = async () => {
    const gen = model.beginSearch();
    abort.current?.abort();
    const a = new AbortController();
    abort.current = a;
    setSearching(true);
    setError("");
    try {
      const list = await api.searchStocks(q, country, a.signal);
      model.resolveSearch(gen, list);
      if (!a.signal.aborted) setStocks(model.stocks);
    } catch (e) {
      if (!a.signal.aborted) setError(errorText(e));
    } finally {
      if (!a.signal.aborted) setSearching(false);
    }
  };
  const select = async (v: Stock) => {
    abort.current?.abort();
    setStock(v);
    setPrice("");
    setPriceDate("");
    setStocks([]);
    setError("");
    const gen = model.select(v);
    try {
      const response = await api.stockPrice(v.assetId);
      model.resolvePrice(gen, response);
      if (model.selected?.assetId === v.assetId) {
        setPrice(model.unitPrice);
        setPriceDate(response.baseDate);
      }
    } catch (e) {
      if (model.selected?.assetId === v.assetId)
        setError(
          `종가를 불러오지 못했어요. 단가를 직접 입력할 수 있습니다. ${errorText(e)}`,
        );
    }
  };
  const submit = async () => {
    setError("");
    if (!stock) {
      setError("먼저 종목을 선택해 주세요.");
      return;
    }
    setBusy(true);
    try {
      if (!/^[1-9]\d*$/.test(quantity))
        throw new Error("수량은 1 이상의 정수로 입력해 주세요.");
      await onSave({
        id: initial?.id ?? Date.now(),
        stock,
        type,
        date,
        quantity: Number(quantity),
        unitPrice: price,
        fee,
        tax,
        ...(fx ? { exchangeRate: fx } : {}),
      });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.modalHeader}>
        <Text accessibilityRole="header" style={s.heading}>
          {initial?.unitPrice ? "거래 수정" : "거래 기록"}
        </Text>
        <Button title="닫기" secondary onPress={onClose} />
      </View>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={s.muted}>
          입력한 거래로 보유 수량과 평균 매입가를 계산합니다.
        </Text>
        {stock ? (
          <Section
            title={stock.name}
            detail={`${stock.assetCode} · ${stock.market}`}
          >
            <Button
              title="다른 종목 선택"
              secondary
              onPress={() => {
                setStock(null);
                model.beginSearch();
                model.select(stock);
              }}
              disabled={!!initial?.unitPrice}
            />
          </Section>
        ) : (
          <Section title="종목 찾기">
            <View style={{ flexDirection: "row", gap: 8 }}>
              {(["KR", "US"] as const).map((k) => (
                <Chip
                  key={k}
                  title={k === "KR" ? "국내" : "미국"}
                  selected={country === k}
                  onPress={() => {
                    setCountry(k);
                    model.beginSearch();
                    abort.current?.abort();
                    setSearching(false);
                    setStocks([]);
                  }}
                />
              ))}
            </View>
            <Field
              label="종목 이름 또는 코드"
              value={q}
              onChangeText={setQ}
              returnKeyType="search"
              onSubmitEditing={search}
            />
            <Button
              title="종목 검색"
              disabled={searching || !q.trim()}
              onPress={() => void search()}
            />
            {searching && <ActivityIndicator />}
            {stocks.map((v) => (
              <Button
                key={v.assetId}
                title={`${v.name} · ${v.assetCode}`}
                secondary
                onPress={() => void select(v)}
              />
            ))}
          </Section>
        )}
        <View style={{ flexDirection: "row", gap: 8 }}>
          {(["BUY", "SELL"] as const).map((v) => (
            <Chip
              key={v}
              title={v === "BUY" ? "매수" : "매도"}
              selected={type === v}
              onPress={() => {
                if (!initial?.unitPrice) setType(v);
              }}
            />
          ))}
        </View>
        <Field
          label="거래일 (YYYY-MM-DD)"
          value={date}
          onChangeText={setDate}
          autoCapitalize="none"
        />
        <Field
          label="수량 (주)"
          keyboardType="number-pad"
          value={quantity}
          onChangeText={setQuantity}
        />
        <Field
          label={`단가 (${stock?.market === "KOSPI" || stock?.market === "KOSDAQ" ? "KRW" : "USD / KRW"})`}
          keyboardType="decimal-pad"
          value={price}
          onChangeText={(v) => {
            model.typePrice(v);
            setPrice(v);
          }}
        />
        {!!priceDate && (
          <Text style={s.caption}>
            {priceDate} 최근 저장 종가 · 직접 수정 가능
          </Text>
        )}
        <View style={styles.twoCols}>
          <View style={{ flex: 1 }}>
            <Field
              label="수수료"
              keyboardType="decimal-pad"
              value={fee}
              onChangeText={setFee}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Field
              label="세금"
              keyboardType="decimal-pad"
              value={tax}
              onChangeText={setTax}
            />
          </View>
        </View>
        {stock && !["KOSPI", "KOSDAQ"].includes(stock.market) && (
          <>
            <Field
              label="거래 환율 (USD/KRW)"
              keyboardType="decimal-pad"
              value={fx}
              onChangeText={setFx}
            />
            <Button
              title="해당 거래일 환율 불러오기"
              secondary
              onPress={() => {
                api
                  .call("fx", { query: { date } })
                  .then((v: any) => setFx(String(v.rate)))
                  .catch((e) => setError(errorText(e)));
              }}
            />
          </>
        )}
        {!!error && (
          <Text
            accessibilityRole="alert"
            style={{ color: c.danger, lineHeight: 23 }}
          >
            {error}
          </Text>
        )}
        <Button
          title={busy ? "저장 중…" : "거래 저장"}
          disabled={busy || !stock}
          onPress={() => void submit()}
        />
        <Text style={s.caption}>
          매수·매도 이후의 원장 정합성을 확인하며, 초과 매도는 저장하지
          않습니다.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
function More({
  api,
  profile,
  baseURL,
  setBaseURL,
  refreshProfile,
  openPanel,
}: any) {
  const [url, setUrl] = useState(baseURL),
    [nickname, setNickname] = useState(profile?.nickname ?? ""),
    [feedback, setFeedback] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => setNickname(profile?.nickname ?? ""), [profile]);
  const run = async (fn: () => Promise<unknown>, success: string) => {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      await fn();
      setMessage(success);
    } catch (e) {
      setMessage(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const login = async () => {
    const { createNativeAuth, validateNativeCallback, AUTH_CALLBACK } =
      await import("./src/auth");
    const attempt = await createNativeAuth(baseURL);
    const response = await WebBrowser.openAuthSessionAsync(
      attempt.url,
      AUTH_CALLBACK,
    );
    if (response.type !== "success") return;
    const body = validateNativeCallback(response.url, attempt);
    await api.call("mobileExchange", { body });
    await refreshProfile();
  };
  return (
    <Page
      title={
        profile
          ? `${profile.nickname ?? "투자자"}님, 반가워요.`
          : "나만의 투자 기록을 이어가세요."
      }
      eyebrow="MY DAYNOMY"
    >
      <Section
        title="계정"
        detail={
          profile
            ? "회원 기록은 서버에 저장됩니다."
            : "게스트 기록은 이 기기에만 저장됩니다. 로그인하면 회원 포트폴리오를 불러옵니다."
        }
      >
        {profile ? (
          <>
            <Field
              label="닉네임"
              value={nickname}
              maxLength={20}
              onChangeText={setNickname}
            />
            <Button
              title="닉네임 저장"
              disabled={busy || !nickname.trim()}
              onPress={() =>
                void run(async () => {
                  await api.call("updateProfile", {
                    body: { nickname: nickname.trim() },
                  });
                  await refreshProfile();
                }, "닉네임을 변경했습니다.")
              }
            />
            <Button
              title="로그아웃"
              secondary
              disabled={busy}
              onPress={() =>
                void run(async () => {
                  await api.call("logout");
                  api.invalidateSession();
                  await refreshProfile();
                }, "로그아웃했습니다.")
              }
            />
            <Button
              title="회원 탈퇴"
              secondary
              disabled={busy}
              onPress={() =>
                Alert.alert(
                  "회원 탈퇴",
                  "계정과 회원 데이터가 삭제됩니다. 계속할까요?",
                  [
                    { text: "취소", style: "cancel" },
                    {
                      text: "탈퇴",
                      style: "destructive",
                      onPress: () =>
                        void run(async () => {
                          await api.call("withdraw");
                          api.invalidateSession();
                          await refreshProfile();
                        }, "탈퇴 처리했습니다."),
                    },
                  ],
                )
              }
            />
          </>
        ) : (
          <>
            <Button
              title="Google로 로그인"
              disabled={busy || Platform.OS === "web"}
              onPress={() => void run(login, "로그인 상태를 확인했습니다.")}
            />
            {Platform.OS === "web" && (
              <Text style={s.caption}>
                외부 브라우저 로그인은 Android/iOS 개발 빌드에서 이용하세요.
              </Text>
            )}
            <Text style={s.caption}>
              외부 브라우저에서 안전하게 인증합니다. 게스트 데이터는 자동으로
              회원 계정에 합쳐지지 않습니다.
            </Text>
          </>
        )}
      </Section>
      <Section title="의견을 들려주세요">
        <Field
          label="피드백 내용 (최대 2,000자)"
          value={feedback}
          onChangeText={setFeedback}
          maxLength={2000}
          multiline
          placeholder="더 나은 DAYNOMY를 위한 의견"
        />
        <Button
          title="피드백 보내기"
          disabled={busy || !feedback.trim()}
          onPress={() =>
            void run(async () => {
              await api.call("feedback", {
                body: { content: feedback.trim() },
              });
              setFeedback("");
            }, "소중한 의견을 전달했습니다.")
          }
        />
      </Section>
      {(profile?.role === "ADMIN" || profile?.roles?.includes("ADMIN")) && (
        <Section title="관리자">
          <Button
            title="뉴스·피드백 편집"
            secondary
            onPress={() => openPanel({ title: "관리자", admin: true })}
          />
          <Button
            title="뉴스 관리"
            secondary
            onPress={() =>
              openPanel({
                title: "뉴스 관리",
                name: "adminNews",
                query: { page: "1", size: "30" },
              })
            }
          />
          <Button
            title="피드백 관리"
            secondary
            onPress={() =>
              openPanel({
                title: "피드백 관리",
                name: "adminFeedbacks",
                query: { page: "1", size: "30" },
              })
            }
          />
          <Button
            title="인물 관리"
            secondary
            onPress={() =>
              openPanel({ title: "인물 관리", name: "adminPeople" })
            }
          />
          <Button
            title="게시 후보 큐"
            secondary
            onPress={() =>
              openPanel({ title: "게시 후보 큐", name: "adminAllCandidates" })
            }
          />
        </Section>
      )}
      <Section
        title="앱 연결 설정"
        detail="실행 중인 DAYNOMY 백엔드 주소를 입력하세요."
      >
        <Field
          label="API 서버 주소"
          value={url}
          onChangeText={setUrl}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <Button
          title="서버 연결 변경"
          secondary
          disabled={busy}
          onPress={() => {
            try {
              new APIClient({ baseURL: url });
              setBaseURL(url);
              setMessage("서버 주소를 변경했습니다.");
            } catch (e) {
              setMessage(errorText(e));
            }
          }}
        />
        <Text selectable style={s.caption}>
          {baseURL}
        </Text>
        <Text style={s.caption}>
          게스트 기록은 보존됩니다. 로그인 세션은 앱 종료 후 유지되지 않을 수
          있습니다.
        </Text>
      </Section>
      {!!message && (
        <View accessibilityLiveRegion="polite" style={styles.notice}>
          <Text style={s.body}>{message}</Text>
        </View>
      )}
    </Page>
  );
}
const labels: Record<string, string> = {
  title: "제목",
  summary: "요약",
  content: "본문",
  description: "설명",
  publishedAt: "발행일",
  createdAt: "등록일",
  category: "분류",
  name: "이름",
  nickname: "닉네임",
  market: "시장",
  assetCode: "종목 코드",
  quantity: "수량",
  averagePurchasePrice: "평균 매입가",
  totalEvaluationAmount: "총 평가금액",
  totalPurchaseAmount: "총 매입금액",
  totalProfitLoss: "총 손익",
  totalReturnRate: "수익률",
  baseDate: "기준일",
  priceBaseDate: "가격 기준일",
  closePrice: "종가",
  returnRate: "수익률",
  profitLoss: "손익",
  overallImpact: "종합 분석",
  issueSummary: "이슈",
  expectedReaction: "예상 반응",
  outlook: "전망",
  reason: "근거",
  evidenceSentence: "근거 문장",
  factQuote: "인용 근거",
  sources: "출처",
  assetName: "종목",
  weight: "비중",
  impacts: "자산별 영향",
  holdings: "보유 종목",
  events: "일정",
  keywords: "키워드",
  marketAnalysis: "시장 분석",
  sourceUrl: "원문",
  url: "링크",
  status: "상태",
  tradeDate: "거래일",
  type: "유형",
  unitPrice: "단가",
  fee: "수수료",
  tax: "세금",
  exchangeRate: "환율",
  items: "목록",
  people: "인물",
  points: "자산 추이",
  currentPoint: "현재 평가",
  history: "변경 이력",
  analysis: "분석",
  portfolio: "포트폴리오",
  page: "페이지",
  hasNext: "다음 페이지",
  direction: "방향",
  impactLevel: "영향 수준",
  coverage: "분석 범위",
  analyzedAt: "분석 시각",
};
function openExternal(url: unknown) {
  if (typeof url !== "string" || !/^https?:\/\//i.test(url)) {
    Alert.alert("링크를 열 수 없습니다", "유효한 웹 주소가 아닙니다.");
    return;
  }
  void Linking.openURL(url).catch(() =>
    Alert.alert("링크를 열 수 없습니다", "다른 브라우저에서 확인해 주세요."),
  );
}
function plain(text: string) {
  return text
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s{3,}/g, "\n\n");
}
function DataView({ value, depth = 0 }: { value: any; depth?: number }) {
  if (value == null)
    return <Text style={s.muted}>표시할 정보가 없습니다.</Text>;
  if (depth > 5) return null;
  if (typeof value === "string")
    return /^https?:\/\//.test(value) ? (
      <Button
        title="출처 링크 열기"
        secondary
        onPress={() => openExternal(value)}
      />
    ) : (
      <Text selectable style={s.body}>
        {plain(value)}
      </Text>
    );
  if (typeof value === "number" || typeof value === "boolean")
    return (
      <Text style={s.body}>
        {typeof value === "boolean" ? (value ? "예" : "아니요") : money(value)}
      </Text>
    );
  if (Array.isArray(value))
    return value.length ? (
      <View style={{ gap: 20 }}>
        {value.slice(0, 50).map((v, i) => (
          <View key={i} style={{ gap: 10 }}>
            <DataView value={v} depth={depth + 1} />
            {i < value.length - 1 && <View style={s.divider} />}
          </View>
        ))}
      </View>
    ) : (
      <Text style={s.muted}>아직 등록된 항목이 없습니다.</Text>
    );
  return (
    <View style={{ gap: 16 }}>
      {Object.entries(value)
        .filter(
          ([k, v]) =>
            ![
              "id",
              "assetId",
              "newsId",
              "memberId",
              "userId",
              "email",
              "imageUrl",
              "thumbnailUrl",
              "updatedAt",
              "version",
              "size",
              "totalElements",
              "totalPages",
            ].includes(k) &&
            v !== undefined &&
            v !== null,
        )
        .map(([key, v]) => (
          <View key={key} style={{ gap: 7 }}>
            <Text style={s.label}>{labels[key] ?? key}</Text>
            <DataView value={v} depth={depth + 1} />
          </View>
        ))}
    </View>
  );
}
function Detail({
  api,
  panel,
  close,
}: {
  api: APIClient;
  panel: Panel;
  close: () => void;
}) {
  const result = useLoad(
    () =>
      panel.path
        ? api.request(panel.path, { query: panel.query })
        : panel.name
          ? api.call(panel.name, { id: panel.id, query: panel.query })
          : Promise.resolve(
              panel.data ?? {
                안내: "보유 종목이 있다면 내 자산 화면의 분석하기를 이용해 주세요.",
              },
            ),
    [api, panel],
  );
  return (
    <View style={{ flex: 1 }}>
      <View style={styles.modalHeader}>
        <Text accessibilityRole="header" style={[s.heading, { flex: 1 }]}>
          {panel.title}
        </Text>
        <Button title="닫기" secondary onPress={close} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <State {...result} retry={result.reload} />
        {result.data && (
          <Section title={panel.title}>
            <DataView value={result.data} />
          </Section>
        )}
        {panel.name === "newsDetail" && panel.id && (
          <>
            <Related
              api={api}
              name="keywords"
              id={panel.id}
              title="관련 키워드"
            />
            <Related
              api={api}
              name="marketAnalysis"
              id={panel.id}
              title="시장 분석"
            />
          </>
        )}
      </ScrollView>
    </View>
  );
}
function Related({ api, name, id, title }: any) {
  const result = useLoad(() => api.call(name, { id }), [api, name, id]);
  return (
    <Section title={title}>
      <State {...result} retry={result.reload} />
      {result.data && <DataView value={result.data} />}
    </Section>
  );
}
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.bg },
  app: { flex: 1 },
  brand: {
    minHeight: 64,
    paddingHorizontal: 24,
    paddingVertical: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    backgroundColor: c.surface,
    borderBottomWidth: 1,
    borderBottomColor: c.line,
  },
  logo: { fontSize: 20, fontWeight: "900", letterSpacing: -1, color: c.ink },
  mode: { flexDirection: "row", alignItems: "center", gap: 6 },
  dot: { height: 5, width: 5, borderRadius: 3, backgroundColor: c.accent },
  content: { padding: 20, gap: 20, paddingBottom: 40 },
  pageTitle: {
    fontSize: 30,
    lineHeight: 40,
    fontWeight: "800",
    letterSpacing: -1.2,
    color: c.ink,
  },
  balance: {
    backgroundColor: c.accent,
    borderRadius: 20,
    padding: 24,
    gap: 18,
  },
  balanceValue: {
    fontSize: 35,
    fontWeight: "800",
    color: "#FFF",
    letterSpacing: -1,
  },
  nav: {
    flexDirection: "row",
    paddingHorizontal: 8,
    paddingTop: 8,
    paddingBottom: 8,
    backgroundColor: c.surface,
    borderTopWidth: 1,
    borderTopColor: c.line,
  },
  navItem: {
    flex: 1,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
  },
  holding: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 8,
  },
  stockMark: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: c.soft,
    alignItems: "center",
    justifyContent: "center",
  },
  newsCard: {
    backgroundColor: c.surface,
    padding: 24,
    borderRadius: 18,
    gap: 18,
  },
  modalHeader: {
    padding: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: c.line,
    gap: 12,
  },
  twoCols: { flexDirection: "row", gap: 12 },
  notice: { padding: 20, borderRadius: 16, backgroundColor: c.soft },
});
