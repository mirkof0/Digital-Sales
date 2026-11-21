"""Project summary: does the email work, for whom, and who should get it?

One page in the style of the homepage (mirkof0.github.io/homepage). It reads only the tables in
results/, which the pipeline writes (`uv run digital-sales`). Run it with:
    uv run streamlit run app/streamlit_app.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

APP_DIR = Path(__file__).resolve().parent
RESULTS = APP_DIR.parent / "results"
HOMEPAGE = "https://mirkof0.github.io/homepage/"

# Colour tokens of the homepage (homepage/assets/style.css), for the light and the dark theme
LIGHT = {
    "page": "#d6e3d7", "panel": "#ffffff", "soft": "#f1f5f1", "ink": "#0f110f", "ink_2": "#2d332e",
    "muted": "#7d857f", "line": "#e6eae6", "line_strong": "#d0d7d1", "sage": "#8fb39b", "sage_2": "#a3b9a8",
    "sage_deep": "#4f7a5f", "btn": "#0f110f", "btn_fg": "#ffffff", "contact_bg": "#0f110f", "footer_ink": "#3d4b41",
    "sphere": "radial-gradient(circle at 34% 30%, #ffffff 0%, #ededed 28%, #bfbfbf 70%, #9b9b9b 100%)",
    "sphere_sage": "radial-gradient(circle at 34% 30%, #f7fbf7 0%, #d2e2d5 30%, #95b49d 76%, #7a9b83 100%)",
}
DARK = {
    "page": "#0a0d0b", "panel": "#131915", "soft": "#1a221c", "ink": "#edf2ee", "ink_2": "#cbd5cd",
    "muted": "#8e9a91", "line": "#232c25", "line_strong": "#33403a", "sage": "#9cc2a8", "sage_2": "#6f8f78",
    "sage_deep": "#9cc2a8", "btn": "#edf2ee", "btn_fg": "#0a0d0b", "contact_bg": "#1c2a21", "footer_ink": "#8e9a91",
    "sphere": "radial-gradient(circle at 34% 30%, #7a857d 0%, #444f47 34%, #232b25 78%, #181e1a 100%)",
    "sphere_sage": "radial-gradient(circle at 34% 30%, #e1efe4 0%, #9cc2a8 34%, #4c6d56 82%, #3a5543 100%)",
}

# Data colours: two greens that match the page. They are close in lightness, so a second cue tells them
# apart: the women's email gets striped bars and diamond markers. INK is the theme's text colour (see col()).
SAGE, TEAL, INK = "#709e87", "#378a95", "ink"
EMAILS = {  # email -> (name, colour, bar pattern, marker symbol)
    "mens_email": ("Men's email", SAGE, "", "circle"),
    "womens_email": ("Women's email", TEAL, "/", "diamond"),
}

# outcome -> (label, scale for display, unit, decimals)
OUTCOMES = {
    "visit": ("Visit rate", 100, "pp", 1),
    "conversion": ("Purchase rate", 100, "pp", 2),
    "spend": ("Revenue per customer", 1, "$", 2),
}

# display name -> (name in the results tables, colour, card title, how it orders customers)
RANKINGS = {
    "Uplift model": ("T-learner uplift", SAGE, "The uplift model",
                     "Customers with the largest predicted uplift first."),
    "Response model": ("Response model", TEAL, "A response model",
                        "Customers with the highest chance of visiting if emailed first: model A alone."),
    "Simple rule": ("Buyer-type rule", INK, "The rule from section 02",
                    "“Both” buyers first, then everyone else in random order."),
}
RANK_SYMBOL = {"Uplift model": "circle", "Response model": "diamond", "Simple rule": "square"}
TABLE_NAME = {table: display for display, (table, *_) in RANKINGS.items()}


# --- Helpers ---

@st.cache_data
def load(name: str) -> pd.DataFrame:
    """One results table, read once and then served from the cache."""
    return pd.read_csv(RESULTS / f"{name}.csv")


def tokens() -> dict[str, str]:
    """Colour tokens of the theme the viewer sees."""
    return DARK if st.context.theme.type == "dark" else LIGHT


def col(color: str) -> str:
    """A data colour, with INK resolved to the active theme's text colour."""
    return tokens()["ink_2"] if color == INK else color


def inject_theme() -> None:
    """Homepage colour tokens for the active theme, then the stylesheet that uses them."""
    css = "".join(f"--{name.replace('_', '-')}:{value};" for name, value in tokens().items())
    st.html(f"<style>:root{{{css}}}</style>")
    st.html(APP_DIR / "style.css")


def html(body: str, script: str = "") -> None:
    """A block of the page's own HTML (styled by style.css), with an optional script of our own."""
    st.html(f'<div class="sx">{body}</div>{script}', unsafe_allow_javascript=bool(script))


# Streamlit's dropdown is a type-to-search box. filter_mode=None stops the filtering, but typed letters still
# show up in the box: this cancels every text edit in a dropdown (typing, pasting, dropping, Backspace), so it
# works as a plain dropdown; arrows and Enter still pick options. Added once per page; the flag stops it from
# stacking up on reruns.
PLAIN_DROPDOWNS = """<script>
if (!window.plainDropdowns) {
  window.plainDropdowns = true;
  document.addEventListener("beforeinput", (e) => {
    if (e.target.closest && e.target.closest('[data-testid="stSelectbox"]')) e.preventDefault();
  }, true);
}
</script>"""


def section_head(overline: str, title: str, anchor: str, lead: str = "") -> None:
    lead_html = f'<p class="lead">{lead}</p>' if lead else ""
    html(f'<p class="overline"><span class="rule"></span>{overline}</p>'
         f'<h2 class="sec-title" id="{anchor}">{title}</h2>{lead_html}')


def fmt_value(outcome: str, x: float) -> str:
    _, scale, unit, dec = OUTCOMES[outcome]
    return f"${x:,.{dec}f}" if unit == "$" else f"{x * scale:.{dec}f}%"


def fmt_lift(outcome: str, x: float) -> str:
    """Signed lift with its unit: +7.7 pp, +$0.77."""
    _, scale, unit, dec = OUTCOMES[outcome]
    sign = "−" if x < 0 else "+"
    return f"{sign}${abs(x):,.{dec}f}" if unit == "$" else f"{sign}{abs(x) * scale:.{dec}f} pp"


def fmt_money(x: float, signed: bool = False) -> str:
    """$97, −$115; with signed=True also +$12."""
    sign = "−" if x < 0 else ("+" if signed else "")
    return f"{sign}${abs(x):,.0f}"


def style(fig: go.Figure, height: int, title: str | None = None, label_room: int | None = None) -> go.Figure:
    """Charts in the page's colours: transparent background, Sora, recessive grid.

    label_room: fixed width in px for text labels on the y-axis. Plotly measures labels before the Sora
    font loads, so automatic room clips long labels.
    """
    t = tokens()
    has_legend = sum(trace.showlegend is not False for trace in fig.data) > 1
    top = 36 + (34 if title else 0) + (30 if has_legend else 0)    # room for the title above the legend
    fig.update_layout(
        template="plotly_white", height=height,
        font=dict(family="Sora, sans-serif", size=12.5, color=t["muted"]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=t["ink_2"])),
        margin=dict(l=8, r=8, t=top, b=8),
        hoverlabel=dict(bgcolor=t["panel"], bordercolor=t["line_strong"],
                        font=dict(family="Sora, sans-serif", color=t["ink"])),
    )
    if has_legend:   # fixed entry width: Plotly measures names before Sora loads and would clip them
        names = [trace.name for trace in fig.data if trace.showlegend is not False and trace.name]
        fig.update_layout(legend=dict(entrywidthmode="pixels", entrywidth=max(map(len, names)) * 8 + 44))
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=15, color=t["ink"]), x=0, xanchor="left",
                                     y=1, yref="container", yanchor="top", pad=dict(t=8)))
    for axes in (fig.update_xaxes, fig.update_yaxes):
        axes(gridcolor=t["line"], linecolor=t["line_strong"], zerolinecolor=t["line_strong"],
             title_font=dict(color=t["muted"]), tickfont=dict(color=t["muted"]))
    if label_room:
        fig.update_layout(margin_l=label_room)
        fig.update_xaxes(automargin="bottom")
        fig.update_yaxes(automargin=False)
    return fig


def rule_per_email(curves: pd.DataFrame, margin: float) -> tuple[float, float, float]:
    """The simple rule's calculated line, read back from the results table.

    It is two straight segments (src/digital_sales/uplift.py, block_line). Returns the share of "Both" buyers
    (where the segments meet) and what an email earns before its cost to a "Both" buyer and to anyone else.
    """
    rule = curves[curves["ranking"] == RANKINGS["Simple rule"][0]]
    rx, rr = rule["share_emailed"].to_numpy(), rule["extra_revenue_per_1000_smoothed"].to_numpy()
    slope_both = rr[1] / rx[1]                                    # first segment, from 0
    slope_rest = (rr[-1] - rr[-2]) / (rx[-1] - rx[-2])             # last segment
    corner = (rr[-1] - slope_rest) / (slope_both - slope_rest)     # where the two segments meet
    return corner, margin * slope_both / 1000, margin * slope_rest / 1000


def chart(fig: go.Figure) -> None:
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False})


def panel(name: str):
    """A white rounded panel, as on the homepage (styled through its st-key-panel-* class)."""
    return st.container(key=f"panel-{name}")


# --- Page sections ---

# Skills shown at the top of the page, as on the WaterMap project page
SKILLS = {
    "Statistics": ["A/B testing", "Multiple testing", "Interaction tests", "Bootstrap"],
    "Modelling": ["T-learner", "Logistic regression", "Cross-validation"],
    "Coding": ["Python", "SQL", "DuckDB", "pandas", "scikit-learn", "Plotly", "Streamlit"],
}


def hero(lifts: pd.DataFrame, het: pd.DataFrame) -> None:
    men = lifts[(lifts["reference"] == "no_email") & (lifts["treated"] == "mens_email")].set_index("outcome")
    n_features = het["dimension"].nunique()
    n_sig = het.loc[het["p_holm"] < 0.05, "dimension"].nunique()      # features where the lift differs
    skills = "".join(f'<div><dt>{group}</dt><dd>{"".join(f"<span class=skill>{s}</span>" for s in items)}</dd></div>'
                     for group, items in SKILLS.items())
    html(f"""
    <nav class="nav">
      <a class="brand">Uplift Modeling</a>
      <div class="nav-links">
        <a href="#sec-data">The data</a><a href="#sec-effect">Does it work?</a><a href="#sec-segments">For whom?</a>
        <a href="#sec-model">The model</a><a href="#sec-simulator">Simulator</a><a href="#sec-method">How it's built</a>
      </div>
    </nav>
    <dl class="skills" aria-label="Skills used in this project">{skills}</dl>
    <div class="hero" id="top">
      <h1>Who should get the email?</h1>
      <p class="lead">An online retailer emailed some customers and not others, chosen at random. Some people received
        an email for men and some others an email for women. This project
        measures what the email changed, finds out for whom it works best, and asks whether it pays to email only
        some customers instead of everyone.</p>
      <div class="actions">
        <a class="pill pill-dark" href="#sec-data">Read the summary ↓</a>
        <a class="pill pill-outline" href="#sec-simulator">Try the simulator ↓</a>
      </div>
      <div class="stats">
        <div class="stat"><p class="stat-num"><span class="sphere"></span>
          {men.loc['visit', 'reference_value']:.1%} → {men.loc['visit', 'treated_value']:.1%}</p>
          <p class="stat-text"> Percentages of customers who visited the website in the two weeks after the campaign: without receiving an email and after receiving the men's email.</p></div>
        <div class="stat"><p class="stat-num"><span class="sphere sphere-sage"></span>
          +${men.loc['spend', 'abs_lift']:.2f}</p>
          <p class="stat-text">extra revenue per customer from the men's email, in the same two weeks.</p></div>
        <div class="stat"><p class="stat-num"><span class="sphere"></span>{n_sig} out of {n_features}</p>
          <p class="stat-text">statistically significant customer feature{"" if n_sig == 1 else "s"}: the kind of
          products a customer buys (men's, women's or both). Only this changes how strongly customers respond to
          the email.</p></div>
      </div>
    </div>""")


def data_section() -> None:
    section_head("The data", "64,000 customers, split at random into three groups", "sec-data",
                 "In 2008 an online clothing retailer took 64,000 customers who had bought something in the past "
                 "year and split them at random into three equal groups. One group got an email advertising men's "
                 "merchandise, one an email advertising women's merchandise, and one got no email.")
    html("""
    <div class="cards">
      <div class="card"><p class="num">What we observe</p><h3>Two weeks after the email</h3>
        <p>For every customer: did they visit the website, did they buy something, and how much did they spend.</p></div>
      <div class="card"><p class="num">What we knew before</p><h3>A short customer profile</h3>
        <p>Months since the last purchase, last year's spend, whether they bought men's, women's or both kinds of
        merchandise, how they order (phone, web or both), whether they are new, and where they live.</p></div>
      <div class="card"><p class="num">Why random matters</p><h3>A fair comparison</h3>
        <p>Groups formed at random are alike in everything except the email. So any difference between them in those
        two weeks is caused by the email. This set-up is called an A/B test.</p></div>
    </div>""")


def aim_section() -> None:
    section_head("The aim", "Three questions", "sec-aim",
                 "The goal is to decide who should get the email. That takes three steps.")
    html("""
    <div class="cards">
      <a class="card" href="#sec-effect"><p class="num">01</p><h3>Does the email work?</h3>
        <p>Compare each email group with the group that got no email.</p></a>
      <a class="card" href="#sec-segments"><p class="num">02</p><h3>Does it work better for some customers?</h3>
        <p>Repeat the comparison within groups of similar customers.</p></a>
      <a class="card" href="#sec-model"><p class="num">03</p><h3>Who should get it?</h3>
        <p>Rank customers by how much the email changes their behaviour, then weigh the extra revenue against the
        cost of the emails.</p></a>
    </div>""")


def effect_section(lifts: pd.DataFrame) -> None:
    vs_none = lifts[lifts["reference"] == "no_email"].set_index(["treated", "outcome"])
    men = vs_none.loc["mens_email"]
    section_head("01 · Does the email work?", "Yes, and the men's email works best", "sec-effect")
    html("""
    <div class="prose">
      <p>For each email I compare its group with the no-email group. The difference is the <strong>lift</strong>.
        For shares of customers, like the visit rate, the lift is measured in <strong>percentage points (pp)</strong>:
        going from 10% to 18% is +8 pp.</p>
      <p>Each lift comes with a <strong>95% confidence interval</strong> (CI): the range of values the data are
        compatible with, since we only observe a sample of customers. When the interval stays above zero, the email
        clearly had an effect.</p>
    </div>""")

    rows = []
    for email, (name, color, *_) in EMAILS.items():
        cards = ""
        for outcome in OUTCOMES:
            r = vs_none.loc[(email, outcome)]
            cards += (f'<div class="kpi"><p class="kpi-label">{OUTCOMES[outcome][0]}</p>'
                      f'<p class="kpi-value">{fmt_value(outcome, r["treated_value"])}</p>'
                      f'<p class="kpi-delta"><b>{fmt_lift(outcome, r["abs_lift"])}</b>'
                      f'vs {fmt_value(outcome, r["reference_value"])} without email</p>'
                      f'<p class="kpi-note">95% CI {fmt_lift(outcome, r["abs_ci_low"])} '
                      f'to {fmt_lift(outcome, r["abs_ci_high"])}</p></div>')
        rows.append(f'<div class="kpi-row"><p class="kpi-group"><span class="dot" style="background:{color}"></span>'
                    f'{name} vs no email</p><div class="kpis">{cards}</div></div>')
    html("".join(rows))

    t = tokens()
    # short labels: Plotly measures them before the Sora font loads, so long ones get clipped
    comparisons = [("mens_email", "no_email", "Men's vs none", SAGE, "circle"),
                   ("womens_email", "no_email", "Women's vs none", TEAL, "diamond"),
                   ("mens_email", "womens_email", "Men's vs women's", t["muted"], "square")]
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.05,
                        subplot_titles=[label for label, *_ in OUTCOMES.values()])
    for col, (outcome, (_, scale, unit, _)) in enumerate(OUTCOMES.items(), start=1):
        for treated, reference, label, color, symbol in comparisons:
            r = lifts[(lifts["outcome"] == outcome) & (lifts["treated"] == treated)
                      & (lifts["reference"] == reference)].iloc[0]
            x, low, high = r["abs_lift"] * scale, r["abs_ci_low"] * scale, r["abs_ci_high"] * scale
            fig.add_trace(go.Scatter(
                x=[x], y=[label], mode="markers", showlegend=False,
                marker=dict(size=11, color=color, symbol=symbol, line=dict(width=2, color=t["panel"])),
                error_x=dict(type="data", symmetric=False, array=[high - x], arrayminus=[x - low],
                             thickness=2, width=0, color=color),
                hovertemplate=f"{label}<br>%{{x:+.2f}} {unit}<br>95% CI {low:.2f} to {high:.2f}<extra></extra>",
            ), row=1, col=col)
        fig.add_vline(x=0, line=dict(width=1, color=t["muted"]), row=1, col=col)     # zero = no effect
        fig.update_xaxes(title_text="pp" if unit == "pp" else "$ per customer", rangemode="tozero",
                         zeroline=False, row=1, col=col)
    fig.update_yaxes(autorange="reversed")
    style(fig, 320, label_room=135)
    fig.update_annotations(font=dict(size=14, color=t["ink"]))
    chart(fig)

    n_sig, n = int((lifts["p_holm"] < 0.05).sum()), len(lifts)
    html(f"""
    <div class="prose">
      <p>Both emails raised all three outcomes, and the men's email did more: the visit rate rose from
        {men.loc['visit', 'reference_value']:.1%} to {men.loc['visit', 'treated_value']:.1%} and revenue per customer
        by ${men.loc['spend', 'abs_lift']:.2f}. Testing {n} comparisons at once raises the chance of a false alarm,
        so I used a stricter threshold, the <strong>Holm correction</strong>: {n_sig} of the {n} effects pass it.</p>
      <p class="caption">Before comparing anything, I checked that the random split worked: the three groups have the
        expected sizes and similar customers.</p>
    </div>""")


def segments_section(seg: pd.DataFrame, lifts: pd.DataFrame, het: pd.DataFrame) -> None:
    sig = het[het["p_holm"] < 0.05]
    buyer = seg[seg["dimension"] == "Buyer type"].set_index(["segment", "email"])["abs_lift"] * 100
    both, mens_only = buyer["Both"], buyer["Men's only"]
    others = buyer.drop("Both", level="segment").xs("mens_email", level="email").mean()
    n_dims = seg["dimension"].nunique()
    section_head("02 · Who responds more?", "It works for everyone, and one group responds twice as strongly",
                 "sec-segments")
    html(f"""
    <div class="prose">
      <p>A <strong>segment</strong> is a group of customers who share a feature, for example "last purchase 1–3 months
        ago". I measured the visit lift of both emails in {len(seg) // 2} segments of {n_dims} features. The first pair
        of bars, "All", is the lift over all customers, for reference.</p>
    </div>""")

    # "All customers" first: the reference every segment is compared with
    t = tokens()
    overall = (lifts[(lifts["outcome"] == "visit") & (lifts["reference"] == "no_email")]
               .rename(columns={"treated": "email"}).assign(dimension="Customers", segment="All"))
    plot_df = pd.concat([overall[seg.columns], seg], ignore_index=True)

    # One label per segment; the feature name is a small heading above the first segment of its group.
    # (A two-level axis needs room for both levels and squeezes the chart on phones.)
    rows = plot_df[plot_df["email"] == "mens_email"].reset_index(drop=True)
    first = ~rows["dimension"].duplicated()
    labels = {}
    for r, is_first in zip(rows.itertuples(), first):
        if r.dimension == "Customers":
            labels[(r.dimension, r.segment)] = "All customers"
        elif is_first:
            labels[(r.dimension, r.segment)] = (f"<span style='font-size:10px;color:{t['muted']}'>"
                                                f"{r.dimension.upper()}</span><br>{r.segment}")
        else:
            labels[(r.dimension, r.segment)] = r.segment
    plot_df["label"] = [labels[(d, s)] for d, s in zip(plot_df["dimension"], plot_df["segment"])]

    # Horizontal bars (a forest plot), "All customers" on top as the reference
    fig = go.Figure()
    for email, (name, color, pattern, _) in EMAILS.items():
        d = plot_df[plot_df["email"] == email]
        lift, low, high = (d[c].to_numpy() * 100 for c in ("abs_lift", "abs_ci_low", "abs_ci_high"))
        fig.add_trace(go.Bar(
            name=name, orientation="h", y=d["label"], x=lift,
            marker=dict(color=color, cornerradius=3,      # stripes tell the two greens apart
                        pattern=dict(shape=pattern, fgcolor=t["panel"], size=6, solidity=0.3)),
            error_x=dict(type="data", symmetric=False, array=high - lift, arrayminus=lift - low,
                         color=t["ink_2"], thickness=1.5, width=2),
            hovertext=d["dimension"] + ": " + d["segment"],
            customdata=np.column_stack([low, high, d["treated_value"] * 100, d["reference_value"] * 100]),
            hovertemplate=("<b>%{hovertext}</b><br>" + name + ": %{x:+.1f} pp"
                           "<br>95% CI %{customdata[0]:.1f} to %{customdata[1]:.1f}"
                           "<br>Visit rate %{customdata[2]:.1f}% vs %{customdata[3]:.1f}% with no email"
                           "<extra></extra>"),
        ))
    fig.update_layout(barmode="group", bargap=0.28, bargroupgap=0.06)
    for i in np.flatnonzero(first)[1:]:                       # a thin line between features
        fig.add_shape(type="line", xref="paper", x0=0, x1=1, y0=i - 0.5, y1=i - 0.5,
                      line=dict(color=t["line_strong"], width=1))
    fig.update_xaxes(title_text="pp vs no email", zeroline=True)
    style(fig, 800, "Visit lift by segment (95% CI)", label_room=125)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=12, color=t["ink_2"]))
    chart(fig)

    html(f"""
    <div class="prose">
      <h3>Are the differences real?</h3>
      <p>For each feature, an <strong>interaction test</strong> checks
        whether the lift is the same in all of its segments. That makes {len(het)} tests ({n_dims} features × 3
        comparisons: each email vs no email, and men's vs women's), so I used the Holm correction again.
        Only {', '.join(sig['dimension'].str.lower().unique())} passes:</p>
    </div>
    <ul class="bullets">
      <li><strong>"Both" buyers</strong>, who bought men's <em>and</em> women's merchandise, gain {both['mens_email']:+.1f} pp
        from the men's email, against about {others:+.0f} pp for the other buyer types.</li>
      <li><strong>Men's-only buyers</strong> barely react to the women's email ({mens_only['womens_email']:+.1f} pp).</li>
      <li>Recency, spend, channel, new vs returning and area make no clear difference.</li>
    </ul>""")
    with st.expander("All interaction tests"):
        table = het.assign(
            comparison=het["comparison"].str.replace("womens_email", "women's email")
                                        .str.replace("mens_email", "men's email").str.replace("no_email", "no email"),
            differs=np.where(het["p_holm"] < 0.05, "yes", "no"),
        )[["comparison", "dimension", "p_holm", "differs"]]
        st.dataframe(table, hide_index=True, width="stretch",
                     column_config={"p_holm": st.column_config.NumberColumn("p-value (Holm)", format="%.4f"),
                                    "differs": "Lift differs between segments?"})


def model_section(qini: pd.DataFrame, deciles: pd.DataFrame) -> None:
    section_head("03 · Can a model pick the right customers?", "A model finds the same customers as the simple rule",
                 "sec-model")
    html("""
    <div class="prose">
      <p>Some customers visit whether or not they get an email; emailing them changes nothing. What matters is the
        <strong>uplift</strong>: how much the email raises a customer's chance of visiting. The uplift of a single
        customer can never be observed, because each one either got the email or didn't. It can be estimated for
        customers who look alike. From here on I use the men's email, the one that works best.</p>
    </div>
    <figure class="diagram" aria-label="How the uplift model works">
      <div class="flow">
        <div class="node"><p class="node-title">A customer</p>
          <p>months since the last purchase<br>last year's spend<br>"Both" buyer or not</p></div>
        <div class="arrow" aria-hidden="true">→</div>
        <div class="models">
          <div class="node"><p class="node-title">Model A</p><p>trained on emailed customers</p>
            <p class="node-out">→ chance of visiting <strong>with</strong> the email</p></div>
          <div class="node"><p class="node-title">Model B</p><p>trained on customers without email</p>
            <p class="node-out">→ chance of visiting <strong>without</strong> it</p></div>
        </div>
        <div class="arrow" aria-hidden="true">→</div>
        <div class="node node-dark"><p class="node-title">Uplift = A − B</p>
          <p>the extra chance of visiting caused by the email</p></div>
      </div>
      <figcaption>Each model is a <strong>logistic regression</strong>, the standard model for yes/no outcomes: it turns
        a customer's profile into a probability between 0 and 1. Using two models like this is called a
        <strong>T-learner</strong> ("T" for two).</figcaption>
    </figure>
    <div class="prose">
      <p><strong>Cross-validation</strong> The customers were split into five parts, and each part was scored by models
        trained on the other four. No customer is scored by a model that has seen them,
        so the results below are what to expect on new customers.</p>
      <h3>Three ways to rank customers</h3>
    </div>""")
    cards = "".join(
        f'<div class="card"><p class="num"><span class="dot" style="background:{col(color)}"></span>{name}</p>'
        f'<h3>{title}</h3><p>{how}</p></div>'
        for name, (_, color, title, how) in RANKINGS.items())
    html(f'<div class="cards">{cards}</div>')
    html("""
    <div class="prose">
      <p>A response model is what many campaigns use. It finds customers who would visit anyway as well as
        customers the email moves.</p>
      <h3>How to compare them</h3>
      <p>Email the top of a ranking and count the extra visits, compared with emailing the same number of customers
        picked at random. The <strong>Qini coefficient</strong> averages that gain over every share of customers
        emailed, from 0% to 100%, in extra visits per 1,000 customers. Higher is better; 0 means no better than random.
        Its interval comes from recomputing it on resampled customers (a bootstrap).</p>
    </div>""")

    t = tokens()
    q = qini.set_index("ranking").rename(index=TABLE_NAME)
    names = list(RANKINGS)
    fig = go.Figure()
    for name in names:
        r = q.loc[name]
        fig.add_trace(go.Scatter(
            x=[r["Qini coefficient"]], y=[name], mode="markers", showlegend=False,
            marker=dict(size=12, color=col(RANKINGS[name][1]), symbol=RANK_SYMBOL[name],
                        line=dict(width=2, color=t["panel"])),
            error_x=dict(type="data", symmetric=False, array=[r["95% CI high"] - r["Qini coefficient"]],
                         arrayminus=[r["Qini coefficient"] - r["95% CI low"]], thickness=2, width=0,
                         color=col(RANKINGS[name][1])),
            hovertemplate=(f"{name}: %{{x:.2f}}<br>95% CI {r['95% CI low']:.2f} to {r['95% CI high']:.2f}"
                           "<extra></extra>"),
        ))
    fig.add_vline(x=0, line=dict(width=1, color=t["muted"]))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Extra visits per 1,000 customers, compared with random", rangemode="tozero")
    chart(style(fig, 260, "Qini coefficient with 95% CI", label_room=120))

    diffs = qini.set_index("ranking").drop(index=[RANKINGS[n][0] for n in names])
    unclear = bool(((diffs["95% CI low"] < 0) & (diffs["95% CI high"] > 0)).all())
    beats_random = bool((q.loc[names, "95% CI low"] > 0).all())
    verdict = ("All three rankings beat random targeting, but none is clearly better than the others.")
    top, rest = deciles.iloc[0], deciles.iloc[1:]
    html(f"""
    <div class="prose">
      <p>{verdict}</p>
      <h3>Why the uplift model adds nothing</h3>
      <p>Cutting the model's ranking into ten equal groups (<strong>deciles</strong>, 1 = highest predicted uplift)
        shows where it finds the customers the email moves. The bars are the lift measured in each group; the short
        lines are what the model predicted.</p>
    </div>""")
    lift, low, high = (deciles[c].to_numpy() * 100 for c in ("abs_lift", "abs_ci_low", "abs_ci_high"))
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=deciles["decile"], y=lift, name="Measured lift (95% CI)", marker=dict(color=SAGE, cornerradius=4),
        error_y=dict(type="data", symmetric=False, array=high - lift, arrayminus=lift - low,
                     color=t["ink_2"], thickness=1.5, width=3),
        hovertemplate="Decile %{x}: %{y:+.1f} pp measured<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=deciles["decile"], y=deciles["predicted_uplift"] * 100, name="Predicted uplift", mode="markers",
        marker=dict(color=t["ink"], size=16, symbol="line-ew-open", line=dict(width=2.5)),
        hovertemplate="Decile %{x}: %{y:+.1f} pp predicted<extra></extra>",
    ))
    fig.update_layout(bargap=0.3)
    fig.update_xaxes(title_text="Decile of the uplift model's ranking", dtick=1)
    fig.update_yaxes(title_text="Visit lift, men's email vs no email (pp)")
    chart(style(fig, 380, "Measured vs predicted lift, by decile"))
    html(f"""
    <ul class="bullets">
      <li><strong>The top 10% are exactly the "Both" buyers</strong>: the email adds {top['abs_lift'] * 100:+.1f} pp,
        as the model predicted.</li>
      <li><strong>In the other nine groups it adds {rest['abs_lift'].min() * 100:.0f} to
        {rest['abs_lift'].max() * 100:.0f} pp, with no trend.</strong> Beyond the "Both" buyers the email works about
        equally well on everyone, so there is nothing left to rank: the model reduces to the simple rule.</li>
    </ul>""")


def simulator_section(curves: pd.DataFrame) -> None:
    model = curves[curves["ranking"] == RANKINGS["Uplift model"][0]]
    x0, v0 = model["share_emailed"].to_numpy(), model["extra_visits_per_1000"].to_numpy()
    top10 = float(np.interp(0.10, x0, v0)) / 100            # extra visits per email in the top 10%
    everyone = v0[-1] / 1000
    section_head("04 · Is targeting worth it?", "Simulate the campaign", "sec-simulator")
    html(f"""
    <div class="prose">
      <p>Emailing fewer customers makes each email work harder: in the model's top 10%, {top10:.1%} of the emailed
        customers visit because of the email, against {everyone:.1%} when everyone is emailed. But fewer emails also
        mean fewer extra visits in total. Whether targeting pays depends on money:</p>
      <p class="formula">Profit = margin × extra revenue − cost per email × emails sent</p>
      <p>The <strong>margin</strong> is the share of revenue left as profit after paying for the goods. Pick a ranking,
        the cost of one email, the margin and how many customers to email. Customers are emailed from the top of the
        ranking down.</p>
    </div>""")

    c1, c2, c3, c4 = st.columns(4)
    display = c1.selectbox("Ranking", list(RANKINGS), filter_mode=None,     # a plain dropdown, no typing
                           help="\n\n".join(f"**{k}:** {v[3]}" for k, v in RANKINGS.items()))
    cost = c2.slider("Cost per email ($)", 0.0, 1.0, 0.30, step=0.01)
    margin = c3.slider("Margin (%)", 10, 100, 50, step=5) / 100
    share = c4.slider("Customers emailed (%)", 0, 100, 30, step=1) / 100

    ranking, color, *_ = RANKINGS[display]
    color = col(color)
    d = curves[curves["ranking"] == ranking]
    x = d["share_emailed"].to_numpy()
    revenue = d["extra_revenue_per_1000_smoothed"].to_numpy()
    visits = d["extra_visits_per_1000"].to_numpy()
    profit = margin * revenue - cost * 1000 * x
    at = lambda curve: float(np.interp(share, x, curve))     # value at the chosen share
    profit_here, best = at(profit), int(np.argmax(profit))
    diff = profit_here - profit[-1]
    per_email = at(visits) / (share * 1000) if share > 0 else 0.0

    kpis = [("Emails sent", f"{share * 1000:,.0f}", "per 1,000 customers"),
            ("Extra visits", f"{at(visits):,.0f}", "caused by the email"),
            ("Visit because of it", f"{per_email:.1%}", "of the emailed customers"),
            ("Extra revenue", fmt_money(at(revenue)), "smoothed"),
            ("Profit", fmt_money(profit_here), f'<b class="{"neg" if diff < 0 else ""}">{fmt_money(diff, True)}</b>'
             "vs emailing everyone")]
    html('<div class="kpis kpis-5">' + "".join(
        f'<div class="kpi"><p class="kpi-label">{label}</p><p class="kpi-value">{value}</p>'
        f'<p class="kpi-delta">{note}</p></div>' for label, value, note in kpis) + "</div>", script=PLAIN_DROPDOWNS)

    earned = margin * revenue[-1] / 1000          # what an email earns on average, before its own cost
    loss = x[(profit < 0) & (x > 0)]
    best_text = (f"The most profitable choice is to email {'everyone' if x[best] > 0.995 else f'the top {x[best]:.0%}'}"
                 f" ({fmt_money(profit[best])} per 1,000 customers).")
    if profit[best] <= 0:
        verdict = "At this cost no share of customers makes a profit: better not to email."
    elif len(loss):
        verdict = (f"<strong>Break-even at the top {loss[0]:.0%}.</strong> Emailing more customers than that loses "
                   f"money, because an email earns only ${earned:.2f} on average before its cost of ${cost:.2f}. "
                   + best_text)
    else:
        verdict = (f"<strong>No break-even point:</strong> every share emailed makes a profit, because an email earns "
                   f"${earned:.2f} on average before its cost of ${cost:.2f}. " + best_text)
    html(f'<div class="callout"><span class="dot"></span><p>{verdict}</p></div>')

    t = tokens()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x * 100, y=x * profit[-1], name="Random customers", mode="lines",
        line=dict(color=t["muted"], width=1.5, dash="dash"),
        hovertemplate="Random %{x:.0f}%: %{y:$,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x * 100, y=profit, name=display, mode="lines", line=dict(color=color, width=2.5),
        hovertemplate="Top %{x:.0f}%: %{y:$,.0f}<extra>" + display + "</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[share * 100], y=[profit_here], name="Your choice", mode="markers",
        marker=dict(size=13, color=color, line=dict(width=2, color=t["panel"])),
        hovertemplate="Your choice: top %{x:.0f}%, %{y:$,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[x[best] * 100], y=[profit[best]], name="Most profitable", mode="markers",
        marker=dict(size=13, color=color, symbol="diamond", line=dict(width=2, color=t["panel"])),
        hovertemplate="Most profitable: top %{x:.0f}%, %{y:$,.0f}<extra></extra>",
    ))
    fig.update_xaxes(title_text="Customers emailed, from the top of the ranking (%)", range=[0, 101],
                     tickvals=list(range(0, 101, 20)))
    fig.update_yaxes(title_text="Profit per 1,000 customers ($)", zeroline=True, zerolinewidth=1.5)
    chart(style(fig, 420, f"Profit by share of customers emailed (${cost:.2f} per email, margin {margin:.0%})"))
    html("""<p class="caption">The dashed line emails the same number of customers picked at random: a straight line
      to the profit of emailing everyone. The gap between the two lines is what the ranking adds. Revenue is noisy,
      because only about 1 customer in 100 buys, so the two models' revenue curves are smoothed: each point is an
      average over its neighbours (about 5% of customers on each side), and peaks narrower than that count as noise.
      The simple rule's line is calculated instead (see below).</p>""")

    corner, both_email, rest_email = rule_per_email(curves, margin)
    with st.expander("Why the simple rule's line is calculated, not measured"):
        html(f"""
        <div class="prose">
          <p>The lines of the uplift model and the response model are <strong>measured</strong>: customers are taken
            in the ranking's order, and at every step the emailed and non-emailed ones are compared. The result is then
            smoothed.</p>
          <p>The simple rule's line is <strong>calculated</strong> from two results of the analysis instead. The rule
            has only two blocks of customers, the "Both" buyers ({corner:.0%} of customers) and everyone else, and
            inside each block the order is random. Measuring it would follow one particular random order and pick up its
            noise, which can put the peak almost anywhere. On average, though, each extra email in a block brings in
            that block's average, so the line is straight within each block. At a {margin:.0%} margin, an email
            earns, before its cost:</p>
        </div>
        <ul class="bullets">
          <li><strong>${both_email:.2f}</strong> when sent to a "Both" buyer;</li>
          <li><strong>${rest_email:.2f}</strong> when sent to anyone else.</li>
        </ul>
        <div class="prose" style="margin-top:12px">
          <p>The two lines meet where the "Both" buyers end, so the best choice is always one of three: email
            everyone if an email costs less than ${rest_email:.2f}, only the "Both" buyers if it costs between
            ${rest_email:.2f} and ${both_email:.2f}, and nobody if it costs more.</p>
        </div>""")


def bottom_line(lifts: pd.DataFrame, seg: pd.DataFrame, curves: pd.DataFrame) -> None:
    men = lifts[(lifts["reference"] == "no_email") & (lifts["treated"] == "mens_email")].set_index("outcome")
    buyer = seg[(seg["dimension"] == "Buyer type") & (seg["email"] == "mens_email")].set_index("segment")["abs_lift"]
    ratio = buyer["Both"] / buyer.drop("Both").mean()
    _, both_email, rest_email = rule_per_email(curves, 0.50)               # at a 50% margin
    html(f"""
    <div class="bottom">
      <p class="overline"><span class="rule"></span>Bottom line</p>
      <h2 class="sec-title">Email everyone, unless emails are expensive</h2>
      <ul class="bullets" style="margin-top:28px">
        <li><strong>The men's email works.</strong> In two weeks it raised the visit rate from
          {men.loc['visit', 'reference_value']:.1%} to {men.loc['visit', 'treated_value']:.1%} and revenue per customer
          by ${men.loc['spend', 'abs_lift']:.2f}.</li>
        <li><strong>It works about equally well on everyone,</strong> except customers who buy both men's and women's
          merchandise, who respond {ratio:.1f}× as strongly.</li>
        <li><strong>A model does not beat the simple rule.</strong> Without an uplift model the optimal rule is to first send the email to the customers
        who bought 'Both' merchandise in the past, and then at random. With the uplift scoring, the customers who get the highest scoring are exactly the
        ones with 'Both' as 'Buyer type' feature. The model found the same result of the data analysis, but doesn't add predictive power.</li>
        <li><strong>Recommendation:</strong> at 50% margin, if an email costs less than about ${rest_email:.2f}, email everyone.
        Between ${rest_email:.2f} and ${both_email:.2f}, only email the 'Both' buyer types, without using an uplift
        model. Above ${both_email:.2f}, don't email.</li>
      </ul>
    </div>""")


def method_section() -> None:
    section_head("How it's built", "From the raw file to this page", "sec-method",
                 "Everything is rebuilt from the public data file by one Python pipeline.")
    html("""
    <dl class="steps">
      <div><dt>1 · Data</dt><dd>Download the file, load it into a DuckDB database with SQL, run data quality
        checks.</dd></div>
      <div><dt>2 · Test readout</dt><dd>Check the random split (group sizes, similar customers), then each lift with
        its confidence interval and the Holm correction.</dd></div>
      <div><dt>3 · Segments</dt><dd>Lifts in 17 segments and interaction tests between them.</dd></div>
      <div><dt>4 · Uplift model</dt><dd>T-learner of two logistic regressions, cross-fitted, compared with two
        baselines using Qini curves and bootstrap intervals.</dd></div>
      <div><dt>5 · This page</dt><dd>The pipeline writes small result tables; this Streamlit page only reads
        them.</dd></div>
    </dl>
    """)


def limits_section() -> None:
    section_head("Limitations", "What this analysis can't tell", "sec-limits")
    html("""
    <ul class="bullets">
      <li>The margin and the email costs are assumptions; the simulator lets you change them, but they don't represent the reality necessarily.</li>
      <li>Revenue is noisy because only about 1 customer in 100 buys, so revenue results are less certain than visit
        results. That is why the models are trained on the visits.</li>
      <li>Only the men's email was modelled; the women's email works less and was left out of the targeting.</li>
    </ul>""")


def footer() -> None:
    html(f"""
    <div class="footer">
      <p>Data: Kevin Hillstrom, MineThatData E-Mail Analytics and Data Mining Challenge (2008).</p>
      <p>A personal portfolio project · <a href="{HOMEPAGE}">More projects on my homepage ↗</a></p>
    </div>""")


# --- Page ---

st.set_page_config(page_title="Who should get the email?", page_icon=":material/mail:", layout="wide")
inject_theme()

lifts, seg, het = load("ab_lifts"), load("segment_lifts"), load("interaction_tests")
qini, deciles, curves = load("qini"), load("deciles"), load("targeting_curves")

with panel("hero"):
    hero(lifts, het)
with panel("data"):
    data_section()
with panel("aim"):
    aim_section()
with panel("effect"):
    effect_section(lifts)
with panel("segments"):
    segments_section(seg, lifts, het)
with panel("model"):
    model_section(qini, deciles)
with panel("simulator"):
    simulator_section(curves)
with panel("bottom"):
    bottom_line(lifts, seg, curves)
with panel("method"):
    method_section()
with panel("limits"):
    limits_section()
footer()
