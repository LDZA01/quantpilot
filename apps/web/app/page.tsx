"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Database,
  FlaskConical,
  Layers,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
type Asset = { symbol: string; name: string; sector: string | null };
type BarRow = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};
type Setup = {
  symbol: string;
  setup: string;
  signal_strength: number;
  supporting_factors: string[];
  risk_factors: string[];
  timestamp: string;
};
type Backtest = {
  id: string;
  symbol: string;
  metrics: Record<string, number | null>;
  equity_curve: { timestamp: string; equity: number; drawdown: number }[];
  trades: {
    entry_timestamp: string;
    exit_timestamp: string;
    net_pnl: number;
    reason: string;
    fees: number;
  }[];
  warnings: string[];
  benchmark: Backtest | null;
  execution: string;
};
type Run = { id: string; symbol: string; created_at: string };
type Job = {
  id: string;
  status: string;
  detail: Record<string, string | number | boolean>;
};
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `${API}${path}`,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
const fmt = (value: number | null | undefined, percent = false) =>
  value == null
    ? "—"
    : percent
      ? `${(value * 100).toFixed(2)}%`
      : value.toLocaleString("en-US", { maximumFractionDigits: 2 });
const navigation = [
  { name: "Overview", icon: Layers },
  { name: "Markets", icon: Activity },
  { name: "Scanner", icon: Search },
  { name: "Stock Detail", icon: BarChart3 },
  { name: "Backtests", icon: FlaskConical },
  { name: "Strategies", icon: ShieldCheck },
  { name: "Settings", icon: Settings },
];
export default function Home() {
  const [page, setPage] = useState("Overview");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [symbol, setSymbol] = useState("AAPL");
  const [loadedSymbol, setLoadedSymbol] = useState("");
  const [bars, setBars] = useState<BarRow[]>([]);
  const [feature, setFeature] = useState<Record<string, number | null>>({});
  const [setups, setSetups] = useState<Setup[]>([]);
  const [scanNotes, setScanNotes] = useState<string[]>([]);
  const [scanDone, setScanDone] = useState(false);
  const [result, setResult] = useState<Backtest | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [strategy, setStrategy] = useState("sma_crossover");
  const [capital, setCapital] = useState(10000);
  const [commission, setCommission] = useState(5);
  const [slippage, setSlippage] = useState(5);
  const [size, setSize] = useState(95);
  const [stop, setStop] = useState("");
  const [take, setTake] = useState("");
  const [start, setStart] = useState("2020-01-01");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const [a, r, j] = await Promise.all([
        request<Asset[]>("/assets"),
        request<Run[]>("/runs"),
        request<Job[]>("/jobs"),
        request("/ready"),
      ]);
      setAssets(a);
      setRuns(r);
      setJobs(j);
      setReady(true);
    } catch (error) {
      setReady(false);
      throw error;
    }
  }, []);
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Asset[]>("/assets"),
      request<Run[]>("/runs"),
      request<Job[]>("/jobs"),
      request("/ready"),
    ])
      .then(([a, r, j]) => {
        if (active) {
          setAssets(a);
          setRuns(r);
          setJobs(j);
          setReady(true);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [refresh]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  async function inspect(s: string) {
    await action(async () => {
      setSymbol(s);
      setBars([]);
      setFeature({});
      const [b, f] = await Promise.all([
        request<BarRow[]>(`/bars/${s}`),
        request<{ latest: Record<string, number | null> }>(`/features/${s}`),
      ]);
      setLoadedSymbol(s);
      setBars(b);
      setFeature(f.latest);
      setPage("Stock Detail");
    });
  }
  const chart = bars.map((b) => ({ ...b, date: b.timestamp.slice(0, 10) }));
  const curve = result?.equity_curve.map((v, i) => ({
    ...v,
    date: v.timestamp.slice(0, 10),
    benchmark: result.benchmark?.equity_curve[i]?.equity,
  }));
  return (
    <div className="shell">
      <aside>
        <Link className="brand" href="/">
          {" "}
          <span className="brand-icon">
            <Activity size={23} />
          </span>
          QuantPilot<span className="beta">MVP</span>
        </Link>
        <div className="workspace-label">PERSONAL WORKSPACE</div>
        <nav>
          {navigation.map(({ name, icon: Icon }) => (
            <button
              key={name}
              onClick={() => setPage(name)}
              className={page === name ? "active" : ""}
            >
              <Icon size={18} />
              {name}
              {page === name && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={21} />
          <strong>Evidence before intuition.</strong>
          <p>
            Explainable signals. Explicit assumptions. Reproducible research.
          </p>
        </div>
        <div className="profile">
          <div className="avatar">QP</div>
          <div>
            Local researcher<small>Personal research environment</small>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Workspace <span>/</span> {page}
          </div>
          <div className="connection">
            <i className={ready ? "online" : ""} />
            {ready ? "Database connected" : "API not ready"}
          </div>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">QUANTITATIVE RESEARCH PLATFORM</div>
              <h1>{page === "Overview" ? "Your research, in focus." : page}</h1>
              <p>Explore the evidence. Understand the assumptions.</p>
            </div>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => action(refresh)}
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
          {error && (
            <div role="alert" className="alert">
              {error}
              <small>
                Check API connectivity, database migrations, and ingestion job
                details. No fallback data is shown.
              </small>
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          {busy && (
            <div role="status" className="loading">
              Working with your research data…
            </div>
          )}
          {(page === "Overview" || page === "Markets") && (
            <>
              <div className="stats">
                <Metric
                  label="Tracked instruments"
                  value={ready ? String(assets.length) : "—"}
                  note="Stored market data"
                />
                <Metric
                  label="Saved backtests"
                  value={ready ? String(runs.length) : "—"}
                  note="Up to 50 recent runs"
                />
                <Metric
                  label="Data frequency"
                  value="Daily"
                  note="Completed US sessions only"
                />
                <Metric
                  label="Execution model"
                  value="Next open"
                  note="Costs included in every run"
                />
              </div>
              <section className="panel ingest">
                <div>
                  <div className="eyebrow">BUILD YOUR DATASET</div>
                  <h2>Start with the market.</h2>
                  <p>
                    Ingest historical US equities and ETFs from Yahoo Finance.
                  </p>
                </div>
                <div className="controls">
                  <label>
                    Symbol
                    <input
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                      maxLength={15}
                    />
                  </label>
                  <label>
                    History from
                    <input
                      type="date"
                      value={start}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <button
                    disabled={busy || !symbol}
                    onClick={() =>
                      action(async () => {
                        const r = await request<Record<string, number>>(
                          "/ingest",
                          { symbol, start },
                        );
                        setNotice(
                          `Ingestion complete: ${r.rows_inserted} inserted, ${r.rows_updated} updated, ${r.rows_unchanged} unchanged.`,
                        );
                        await refresh();
                      })
                    }
                  >
                    <Database size={16} />
                    Ingest data
                  </button>
                </div>
              </section>
              <div className="two-col">
                <section className="panel">
                  <div className="panel-title">
                    <h2>Market library</h2>
                    <span className="tag">USD · DAILY</span>
                  </div>
                  {assets.length ? (
                    assets.map((a) => (
                      <button
                        className="asset-row"
                        key={a.symbol}
                        disabled={busy}
                        onClick={() => inspect(a.symbol)}
                      >
                        <span className="ticker">{a.symbol.slice(0, 2)}</span>
                        <span>
                          <strong>{a.symbol}</strong>
                          <small>{a.name}</small>
                        </span>
                        <span className="asset-sector">
                          {a.sector || "ETF / sector unavailable"}
                        </span>
                        <ArrowUpRight size={17} />
                      </button>
                    ))
                  ) : (
                    <Empty
                      title="Your market library starts here"
                      text="Ingest AAPL, NVDA, SPY or QQQ above. Prices appear only after a successful provider response."
                    />
                  )}
                </section>
                <section className="panel">
                  <div className="panel-title">
                    <h2>Research guardrails</h2>
                    <ShieldCheck size={19} />
                  </div>
                  {[
                    "No generated prices or performance",
                    "Signals evaluated at the close; fills at next open",
                    "Explicit commission and slippage",
                    "Corporate-action revision detection",
                  ].map((s, i) => (
                    <div className="guardrail" key={s}>
                      <span>0{i + 1}</span>
                      {s}
                    </div>
                  ))}
                  <div className="subtle-box">
                    This milestone covers market data, features, scanning and
                    backtesting. Portfolio analytics and ML arrive in later
                    milestones.
                  </div>
                </section>
              </div>
            </>
          )}
          {page === "Stock Detail" && (
            <>
              <section className="panel">
                <div className="panel-title">
                  <h2>{loadedSymbol || symbol} · Price history</h2>
                  <div className="controls">
                    <label>
                      Instrument
                      <select
                        value={symbol}
                        onChange={(e) => setSymbol(e.target.value)}
                      >
                        {!assets.some((a) => a.symbol === symbol) && (
                          <option>{symbol}</option>
                        )}
                        {assets.map((a) => (
                          <option key={a.symbol}>{a.symbol}</option>
                        ))}
                      </select>
                    </label>
                    <button disabled={busy} onClick={() => inspect(symbol)}>
                      Load
                    </button>
                  </div>
                </div>
                {chart.length ? (
                  <>
                    <p className="muted">
                      Split-adjusted daily close · USD · {chart.at(-1)?.date}.
                      Daily volume below.
                    </p>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chart}>
                          <defs>
                            <linearGradient
                              id="price"
                              x1="0"
                              y1="0"
                              x2="0"
                              y2="1"
                            >
                              <stop
                                offset="0%"
                                stopColor="#22c4a0"
                                stopOpacity={0.25}
                              />
                              <stop
                                offset="100%"
                                stopColor="#22c4a0"
                                stopOpacity={0}
                              />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="#edf0f3" vertical={false} />
                          <XAxis dataKey="date" minTickGap={65} />
                          <YAxis domain={["auto", "auto"]} />
                          <Tooltip />
                          <Area
                            dataKey="close"
                            stroke="#0b9b7e"
                            fill="url(#price)"
                            isAnimationActive={false}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="volume-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chart}>
                          <XAxis dataKey="date" hide />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="volume" fill="#a7d9cc" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="feature-grid">
                      {[
                        "close",
                        "sma20",
                        "sma50",
                        "ema20",
                        "rsi",
                        "macd",
                        "atr",
                        "momentum20",
                        "relative_volume",
                        "volatility",
                        "drawdown",
                        "daily_vwap_proxy20",
                      ].map((k) => (
                        <Metric
                          key={k}
                          label={k.replaceAll("_", " ")}
                          value={fmt(
                            feature[k],
                            ["momentum20", "volatility", "drawdown"].includes(
                              k,
                            ),
                          )}
                        />
                      ))}
                    </div>
                  </>
                ) : (
                  <Empty
                    title="Choose an instrument"
                    text="Load stored data to explore price history and quantitative features."
                  />
                )}
              </section>
            </>
          )}
          {page === "Scanner" && (
            <>
              <section className="panel">
                <div className="panel-title">
                  <div>
                    <h2>Rule-based setup scanner</h2>
                    <p>
                      Score = fraction of satisfied rules. It is not a
                      probability of profit.
                    </p>
                  </div>
                  <button
                    disabled={busy || !assets.length}
                    onClick={() =>
                      action(async () => {
                        const r = await request<{
                          results: Setup[];
                          failures: { symbol: string; detail: string }[];
                        }>("/scanner", {
                          symbols: assets.map((a) => a.symbol),
                        });
                        setSetups(r.results);
                        setScanNotes(
                          r.failures.map((f) => `${f.symbol}: ${f.detail}`),
                        );
                        setScanDone(true);
                      })
                    }
                  >
                    <Search size={16} />
                    Scan library
                  </button>
                </div>
                {scanNotes.map((n) => (
                  <p className="alert" key={n}>
                    {n}
                  </p>
                ))}
                {setups.length ? (
                  <div className="setup-grid">
                    {setups.map((s) => (
                      <article className="setup" key={s.symbol + s.setup}>
                        <div className="panel-title">
                          <strong>{s.symbol}</strong>
                          <span className="tag">
                            {s.signal_strength}% rule coverage
                          </span>
                        </div>
                        <h3>{s.setup.replaceAll("_", " ")}</h3>
                        <ul>
                          {s.supporting_factors.map((f) => (
                            <li key={f}>{f}</li>
                          ))}
                        </ul>
                        <div className="risk">
                          {s.risk_factors.map((f) => (
                            <p key={f}>{f}</p>
                          ))}
                        </div>
                        <small>As of {s.timestamp.slice(0, 10)}</small>
                      </article>
                    ))}
                  </div>
                ) : (
                  <Empty
                    title={
                      scanDone
                        ? "No qualifying setups"
                        : "Let the rules do the screening"
                    }
                    text={
                      scanDone
                        ? "Review any data issues above. No qualifying setup is also a valid result."
                        : "Run the scanner on your stored library. Each symbol needs at least 50 sessions."
                    }
                  />
                )}
              </section>
            </>
          )}
          {page === "Backtests" && (
            <>
              <section className="panel">
                <h2>Test a hypothesis</h2>
                <p>
                  Long-only, fractional shares. No leverage. Dividends excluded.
                </p>
                <div className="controls backtest-controls">
                  <label>
                    Symbol
                    <select
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value)}
                    >
                      {!assets.some((a) => a.symbol === symbol) && (
                        <option>{symbol}</option>
                      )}
                      {assets.map((a) => (
                        <option key={a.symbol}>{a.symbol}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Strategy
                    <select
                      value={strategy}
                      onChange={(e) => setStrategy(e.target.value)}
                    >
                      {[
                        "sma_crossover",
                        "rsi_mean_reversion",
                        "momentum",
                        "breakout",
                      ].map((s) => (
                        <option value={s} key={s}>
                          {s.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Initial capital ($)
                    <input
                      type="number"
                      min="1"
                      value={capital}
                      onChange={(e) => setCapital(+e.target.value)}
                    />
                  </label>
                  <label>
                    Commission (bps)
                    <input
                      type="number"
                      min="0"
                      value={commission}
                      onChange={(e) => setCommission(+e.target.value)}
                    />
                  </label>
                  <label>
                    Slippage (bps)
                    <input
                      type="number"
                      min="0"
                      value={slippage}
                      onChange={(e) => setSlippage(+e.target.value)}
                    />
                  </label>
                  <label>
                    Allocation (%)
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={size}
                      onChange={(e) => setSize(+e.target.value)}
                    />
                  </label>
                  <label>
                    Stop loss (%)
                    <input
                      type="number"
                      placeholder="Disabled"
                      value={stop}
                      onChange={(e) => setStop(e.target.value)}
                    />
                  </label>
                  <label>
                    Take profit (%)
                    <input
                      type="number"
                      placeholder="Disabled"
                      value={take}
                      onChange={(e) => setTake(e.target.value)}
                    />
                  </label>
                  <button
                    disabled={busy}
                    onClick={() =>
                      action(async () => {
                        setResult(null);
                        const r = await request<Backtest>("/backtests", {
                          symbol,
                          strategy,
                          initial_capital: capital,
                          commission_bps: commission,
                          slippage_bps: slippage,
                          position_size: size / 100,
                          stop_loss: stop ? Number(stop) / 100 : null,
                          take_profit: take ? Number(take) / 100 : null,
                        });
                        setResult(r);
                        await refresh();
                      })
                    }
                  >
                    <FlaskConical size={16} />
                    Run backtest
                  </button>
                </div>
              </section>
              {result ? (
                <>
                  <div className="stats">
                    {["total_return", "cagr", "sharpe", "max_drawdown"].map(
                      (k) => (
                        <Metric
                          key={k}
                          label={k.replaceAll("_", " ")}
                          value={fmt(result.metrics[k], k !== "sharpe")}
                        />
                      ),
                    )}
                  </div>
                  <section className="panel">
                    <div className="panel-title">
                      <h2>{result.symbol} · Equity curve</h2>
                      <span className="tag">Strategy · green / SPY · gray</span>
                    </div>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={curve}>
                          <CartesianGrid stroke="#edf0f3" vertical={false} />
                          <XAxis dataKey="date" minTickGap={70} />
                          <YAxis domain={["auto", "auto"]} />
                          <Tooltip />
                          <Line
                            type="linear"
                            dataKey="equity"
                            stroke="#079a78"
                            dot={false}
                            isAnimationActive={false}
                          />
                          <Line
                            dataKey="benchmark"
                            stroke="#98a5b5"
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <h3>Drawdown (fraction)</h3>
                    <div className="volume-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={curve}>
                          <XAxis dataKey="date" hide />
                          <YAxis />
                          <Tooltip />
                          <Area
                            dataKey="drawdown"
                            stroke="#db7f6a"
                            fill="#f7e4df"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="feature-grid">
                      {Object.entries(result.metrics).map(([k, v]) => (
                        <Metric
                          key={k}
                          label={k.replaceAll("_", " ")}
                          value={fmt(
                            v,
                            [
                              "total_return",
                              "annualized_return",
                              "cagr",
                              "max_drawdown",
                              "volatility",
                              "win_rate",
                              "loss_rate",
                            ].includes(k),
                          )}
                        />
                      ))}
                    </div>
                    <p className="muted">{result.execution}</p>
                    {result.warnings.map((w) => (
                      <p key={w} className="warning">
                        {w}
                      </p>
                    ))}
                  </section>
                  <section className="panel">
                    <h2>Completed trades</h2>
                    {result.trades.length ? (
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Entry session</th>
                              <th>Exit session</th>
                              <th>Net P&amp;L ($)</th>
                              <th>Fees ($)</th>
                              <th>Exit reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.trades.map((t, i) => (
                              <tr key={i}>
                                <td>{t.entry_timestamp.slice(0, 10)}</td>
                                <td>{t.exit_timestamp.slice(0, 10)}</td>
                                <td>{fmt(t.net_pnl)}</td>
                                <td>{fmt(t.fees)}</td>
                                <td>{t.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p>
                        No completed trades. Open positions are marked to the
                        final close.
                      </p>
                    )}
                  </section>
                </>
              ) : (
                <section className="panel">
                  <Empty
                    title="Make assumptions measurable"
                    text="Choose a strategy and execution costs, then run it against your stored market history."
                  />
                </section>
              )}
              <section className="panel">
                <h2>Saved research runs</h2>
                {runs.map((r) => (
                  <button
                    className="asset-row"
                    key={r.id}
                    disabled={busy}
                    onClick={() =>
                      action(async () =>
                        setResult(await request<Backtest>(`/runs/${r.id}`)),
                      )
                    }
                  >
                    <strong>{r.symbol}</strong>
                    <span>{r.created_at.slice(0, 19)}</span>
                    <small>{r.id.slice(0, 8)}</small>
                    <ArrowUpRight size={16} />
                  </button>
                ))}
              </section>
            </>
          )}
          {page === "Strategies" && (
            <section className="panel">
              <h2>Transparent baseline strategies</h2>
              {[
                [
                  "SMA crossover",
                  "Hold when SMA20 exceeds SMA50; otherwise cash.",
                ],
                [
                  "RSI mean reversion",
                  "Enter below RSI 30; exit above RSI 55. Wilder smoothing, 14 sessions.",
                ],
                [
                  "Momentum",
                  "Hold when the trailing 20-session price return is positive.",
                ],
                [
                  "Breakout",
                  "Enter above the previous 20-session high; exit below SMA20.",
                ],
              ].map(([title, description]) => (
                <div className="strategy" key={title}>
                  <FlaskConical size={20} />
                  <div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                  </div>
                </div>
              ))}
              <div className="subtle-box">
                All decisions use completed bars. Orders execute at the next
                session open. Warm-up periods remain in cash. These are research
                baselines, not validated investment strategies.
              </div>
            </section>
          )}
          {page === "Settings" && (
            <>
              <section className="panel">
                <h2>Environment & methodology</h2>
                <dl>
                  <dt>API</dt>
                  <dd>{API}</dd>
                  <dt>Provider</dt>
                  <dd>Yahoo Finance via yfinance · personal development use</dd>
                  <dt>Price basis</dt>
                  <dd>
                    Split-adjusted daily OHLC; price returns exclude dividends
                  </dd>
                  <dt>Time handling</dt>
                  <dd>
                    UTC midnight session labels; current New York date excluded
                  </dd>
                  <dt>LLM / brokerage</dt>
                  <dd>Not enabled in this milestone</dd>
                </dl>
              </section>
              <section className="panel">
                <h2>Ingestion activity</h2>
                {jobs.length ? (
                  jobs.map((j) => (
                    <div className="job" key={j.id}>
                      <strong>
                        {String(j.detail.symbol)}{" "}
                        <span className="tag">{j.status}</span>
                      </strong>
                      <pre>{JSON.stringify(j.detail, null, 2)}</pre>
                    </div>
                  ))
                ) : (
                  <Empty
                    title="No ingestion jobs yet"
                    text="Provider failures and row counts will appear here."
                  />
                )}
              </section>
            </>
          )}
          <footer>
            <span>
              <ShieldCheck size={14} />
              Personal research & decision support
            </span>
            <span>Historical results do not guarantee future returns.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="metric">
      <div>{label}</div>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <BarChart3 size={30} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
