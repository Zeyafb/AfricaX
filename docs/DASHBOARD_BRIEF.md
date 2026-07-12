# AfricaX — Dashboard v2 brief (please redesign the single-page dashboard)

We built a single-page dashboard, and honestly **it still looks unpolished** — like a
default Streamlit box-grid, not a designed product. Attached are the real current
screenshots (`current-dashboard.png`, `current-rank-view.png`, `current-leaderboard-view.png`).
Please redesign it into something genuinely cohesive and warm. Everything below is real.

## Keep — non-negotiable
- **Consensus RANKING model, NOT star ratings.** Each member drags their *visited* spots
  into order; the group standing is the **median of everyone's normalised ranks**, shown as
  an **X/10** (or 0–100). The reorder ballot and the full editorial leaderboard are their
  own dedicated views, opened from the dashboard.
- **Single-page dashboard** concept (one scroll, tiles).
- **Real data only** — no invented restaurants, photos, reviews, cuisines, or ratings.
  Truth: 5 friends (Fayez, Muhammad, Seth, Ian, Shubham), 5 visited spots
  (Chez Dior/Senegal, Kulan Cafe/Somalia, Calabash/Ghana, King of Koshary/Egypt,
  Fettoosh/Morocco), 6 wishlist spots (DMV area only: VA/DC/MD), 51 African countries.
- **Built in Streamlit** — favour card / column / stack patterns; no bespoke drag-canvas
  or JS-heavy widgets. Custom CSS in `st.markdown` is fine.
- The **Folium Africa map** (green = visited, purple = wishlist, grey = not visited).

## Functionality to include — every feature needs a home in the redesign
Do **not** drop any of these; the layout must give each one a place:

- **Header** — AFRICAX wordmark + "African Restaurant Passport"; the 5 friends as avatars;
  a primary **Rank your spots** action + a secondary **Add spot** action.
- **KPIs** — countries visited (of 51), places visited, wishlist count, and the top
  consensus spot + its score.
- **Map (interactive)** — Africa, 3 states. **Clicking a country selects it** and fills the
  Selected-Country panel.
- **Selected Country panel** — flag/code + name + Visited/Want-to-go pill; the restaurant(s)
  there with **dish chips**, notes, and the **group consensus** (X/10 + how many ranked it);
  a link to all spots in that country.
- **Group Leaderboard (the hero)** — top 3 on the dashboard; **View full leaderboard** opens
  the full editorial ranked list: rank #, restaurant + country, 0–100 **median** with a score
  bar, **ranked-by** avatars, plus **"each person's #1"**.
- **My Rankings** — pick "who are you" → see that member's personal order (top 5).
  **Rank your spots** opens a dedicated **reorder ballot** (drag / up-down); saving recomputes
  the group consensus instantly. This is the one input that lives as its own view.
- **Wishlist & Next Up** — wishlist spots with country + location + a **Maps** link;
  **View full wishlist**.
- **Quick Add Spot** — inline form: country, restaurant, dishes, notes, and a
  **Visited / Wishlist** toggle → adds to the passport. **No rating field** (ranking is separate).
- **Passport Progress** — progress toward all 51 African countries (a ring/meter).
- **Recent Activity** — the most recent visits/additions.
- **Persistence** — data lives in a shared **Google Sheet** (all 5 friends, multi-user).

## What's wrong right now (be blunt — this is the brief)
1. **Ragged, unbalanced tiles.** Row 1 puts a huge map next to a nearly-empty "Selected
   Country" tile → a big block of dead whitespace. Tile heights don't align.
2. **Generic "bordered box" grid.** It reads as default Streamlit: same-weight cards, emoji
   section headers, no real hierarchy. Nothing draws the eye.
3. **The map is oversized** and dominates; everything else feels sparse and secondary by accident.
4. **KPI cards feel default/stock.**
5. **No cohesive type scale or spacing rhythm.** It's tiles floating, not a composition.

## What we want
- A **polished, warm, editorial "restaurant passport" dashboard** — intentional, cohesive,
  friend-group-personal. Not a SaaS admin panel, not default Streamlit.
- **Deliberate hierarchy:** the **map + current group leaderboard** are the hero; wishlist,
  quick-add, activity, and passport-progress are quieter supporting tiles.
- **A balanced grid** — consistent tile heights/rhythm, the map sized sensibly (not
  dominating), and a "Selected Country" panel that looks intentional even before a click.
- Map-first, but **the group ranking/leaderboard should feel like the centrepiece** (it's the
  reason the app exists).
- Keep the little delights that worked in the earlier `AfricaX.dc.html`: code-chip country
  badges, member avatars, dish chips, and the editorial ranked leaderboard.

## Design tokens (in use)
`#2E7D5B` green (visited) · `#8B5FBF` purple (wishlist) · `#E6E6E6` grey (not visited) ·
`#DCEFF9` ocean · text `#1F2328` / muted `#6B7280` · cream accents welcome
(`#F7F3EC`) · **Source Sans 3**. Reduce emoji; if you use icons, one consistent set.

## Deliverable
A **`.dc.html` concept for the single-page dashboard** we can implement in Streamlit — one
composition, tiles aligned to a real grid, with the ranking/leaderboard as the hero.
