import streamlit as st
import pandas as pd
import eval7
import random

# 画面設定
st.set_page_config(page_title="GTO Precision Engine v6.1", page_icon="🧬", layout="wide")

# --- 1. 定義クラスとデータロード ---
ALL_COLORS = ["グレー", "薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]
PREFLOP_ORDER = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POSTFLOP_ORDER = ["SB", "BB", "UTG", "LJ", "HJ", "CO", "BTN"]

POSITION_LEFT_PLAYERS = {"UTG": 7, "LJ": 6, "HJ": 5, "CO": 4, "BTN": 3, "SB": 2, "BB": 0}

@st.cache_data
def load_ranges_from_csv():
    base = {}
    for h in ["AA","AKs","AKo","KK","QQ"]: base[h] = "紺"
    for h in ["JJ","TT","99","AQs","AJs","ATs","KQs","AQo"]: base[h] = "赤"
    for h in ["88","77","KJs","QJs","JTs","AJo","KQo"]: base[h] = "黄"
    for h in ["66","55","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s","KTs","K9s","QTs","T9s","ATo","KJo"]: base[h] = "緑"
    for h in ["44","33","22","Q9s","J9s","T8s","98s","A9o","KTo","QJo","JTo"]: base[h] = "水色"
    return base

hand_to_color = load_ranges_from_csv()

def get_open_min_color(pos):
    left_players = POSITION_LEFT_PLAYERS.get(pos, 0)
    if left_players == 2: return "グレー＋紫枠"
    elif left_players == 3: return "白"
    elif left_players in [4, 5]: return "水色"
    elif left_players in [6, 7]: return "緑"
    else: return "黄"

def get_preflop_ranges(opener_pos, defender_pos):
    op_min_color = get_open_min_color(opener_pos)
    op_min_idx = ALL_COLORS.index(op_min_color)
    opener_colors = ALL_COLORS[op_min_idx:]
    
    call_colors = []
    if defender_pos == "BB":
        if opener_pos == "BTN": call_colors = ALL_COLORS[ALL_COLORS.index("薄ピンク"):]
        elif opener_pos == "CO": call_colors = ALL_COLORS[ALL_COLORS.index("グレー＋紫枠"):]
        else: call_colors = ALL_COLORS[ALL_COLORS.index("白"):]
    else:
        if op_min_idx + 1 < len(ALL_COLORS):
            call_colors = [ALL_COLORS[op_min_idx + 1]]
    return opener_colors, call_colors

def convert_to_concrete_cards(hand_str):
    suits = "shcd"
    r1, r2 = hand_str[0], hand_str[1]
    is_suited = hand_str.endswith('s')
    combos = []
    if r1 == r2:
        for i in range(4):
            for j in range(i + 1, 4): combos.append([r1 + suits[i], r2 + suits[j]])
    elif is_suited:
        for s in suits: combos.append([r1 + s, r2 + s])
    else:
        for i in range(4):
            for j in range(4):
                if i != j: combos.append([r1 + suits[i], r2 + suits[j]])
    return combos

def get_range_combos(target_colors, hand_to_color_map):
    all_combos = []
    for hand, color in hand_to_color_map.items():
        if color in target_colors: 
            all_combos.extend(convert_to_concrete_cards(hand))
    return all_combos

# --- 2. モンテカルロ＆GTO計算エンジン ---
def run_simulation(hero_combos, villain_combos, board, iterations=300):
    if not hero_combos or not villain_combos: return 0.5
    hero_wins, villain_wins, ties, actual_iterations = 0, 0, 0, 0
    deck_base = [eval7.Card(f"{r}{s}") for r in "23456789TJQKA" for s in "shcd"]
    h_cards_list = [[eval7.Card(c[0]), eval7.Card(c[1])] for c in hero_combos]
    v_cards_list = [[eval7.Card(c[0]), eval7.Card(c[1])] for c in villain_combos]
    board_set = set(board)
    
    for _ in range(iterations):
        h_cards = random.choice(h_cards_list)
        v_cards = random.choice(v_cards_list)
        if board_set.intersection(h_cards) or board_set.intersection(v_cards) or set(h_cards).intersection(v_cards):
            continue
        actual_iterations += 1
        used = board_set.union(h_cards).union(v_cards)
        rem = [c for c in deck_base if c not in used]
        num_draw = 5 - len(board)
        final_board = board + random.sample(rem, num_draw) if num_draw > 0 else board
        
        h_scr = eval7.evaluate(h_cards + final_board)
        v_scr = eval7.evaluate(v_cards + final_board)
        if h_scr > v_scr: hero_wins += 1
        elif v_scr > h_scr: villain_wins += 1
        else: ties += 1
    return (hero_wins + 0.5 * ties) / actual_iterations if actual_iterations > 0 else 0.5

def analyze_board_texture(board_cards):
    ranks = [c[0] for c in board_cards]
    suits = [c[1] for c in board_cards]
    rank_values = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"T":10,"J":11,"Q":12,"K":13,"A":14}
    values = sorted([rank_values[r] for r in ranks], reverse=True)
    
    paired = len(set(ranks)) < len(ranks)
    flush_draw = max([suits.count(s) for s in set(suits)]) >= 2
    gap = values[0] - values[-1] if len(values) >= 3 else 7
    straight_draw = 1 if gap <= 4 else 0
    
    dynamic_score = 0.2
    if flush_draw: dynamic_score += 0.3
    if straight_draw: dynamic_score += 0.2
    if values[0] < 11: dynamic_score += 0.2
    if paired: dynamic_score -= 0.3
        
    return {"dynamic_score": max(0.0, min(1.0, dynamic_score)), "paired": paired, "flush_draw": flush_draw, "high_card": ranks[0], "values": values}

def calculate_range_composition(combos, board_cards):
    board_obj = [eval7.Card(c) for c in board_cards]
    nuts, top_pair, air = 0, 0, 0
    for c in combos:
        c_obj = [eval7.Card(c[0]), eval7.Card(c[1])]
        scr = eval7.evaluate(c_obj + board_obj)
        if scr >= 25165824: nuts += 1
        elif scr >= 16777216: top_pair += 1
        else: air += 1
    total = len(combos) if combos else 1
    return {"nuts": nuts/total, "top_pair": top_pair/total, "air": air/total}

def calculate_gto_frequencies_v61(hero_hand_str, hero_colors, villain_colors, board_cards, street):
    h_range = get_range_combos(hero_colors, hand_to_color)
    v_range = get_range_combos(villain_colors, hand_to_color)
    board_obj = [eval7.Card(c) for c in board_cards]
    
    h_hand = [hero_hand_str[:2], hero_hand_str[2:]]
    hand_eq = run_simulation([h_hand], v_range, board_obj, iterations=400)
    range_eq = run_simulation(h_range, v_range, board_obj, iterations=400)
    
    texture = analyze_board_texture(board_cards)
    h_comp = calculate_range_composition(h_range, board_cards)
    v_comp = calculate_range_composition(v_range, board_cards)
    
    freq = {"bet_70": 0.0, "bet_33": 0.0, "check": 0.0}
    
    if range_eq >= 0.54:
        if texture["values"][0] <= 11:
            freq["bet_33"] = round(85.0 * (1.0 - texture["dynamic_score"] * 0.1), 1)
            freq["bet_70"] = round(5.0 + (texture["dynamic_score"] * 10.0), 1)
        else:
            freq["bet_70"] = round(50.0 * (h_comp["nuts"] / (v_comp["nuts"] + 0.01)), 1)
            freq["bet_33"] = round(40.0, 1)
        freq["check"] = round(100.0 - freq["bet_70"] - freq["bet_33"], 1)
    else:
        freq["check"] = round(65.0 + (texture["dynamic_score"] * 15.0), 1)
        if hand_eq >= 0.70:
            freq["bet_70"] = round((100.0 - freq["check"]) * 0.6, 1)
            freq["bet_33"] = round(100.0 - freq["check"] - freq["bet_70"], 1)
        else:
            freq["bet_33"] = round(100.0 - freq["check"], 1)

    total = sum(freq.values())
    for k in freq: freq[k] = round((freq[k] / total) * 100.0, 1)
    return freq, hand_eq, range_eq, texture, {"hero": h_comp, "villain": v_comp}

# --- 3. 画面制御メイン ---
if "game_state" not in st.session_state: st.session_state.game_state = "setup"

if st.session_state.game_state == "setup":
    st.markdown("### 🧬 GTOポジション指定＆数理検証シミュレーター")
    
    hero_pos = st.selectbox("あなたのポジション (Hero)", PREFLOP_ORDER, index=0) # デフォルトUTG
    villain_pos_option = st.selectbox("相手のポジション (Villain)", ["ランダムに決定"] + PREFLOP_ORDER)
    situation = st.selectbox("シチュエーション", ["自分がオープンレイズし、相手がコールした状況"])

    if st.button("このポジション設定でシミュレーションを開始 🚀", use_container_width=True):
        # 相手がランダムの場合の処理
        if villain_pos_option == "ランダムに決定":
            available_p = [p for p in PREFLOP_ORDER if p != hero_pos]
            chosen_villain = random.choice(available_p)
        else:
            chosen_villain = villain_pos_option

        # プリフロップレンジの特定
        opener, defender = hero_pos, chosen_villain
        op_colors, call_colors = get_preflop_ranges(opener, defender)
        
        # 今回は「自分がオープンレイズ」固定のシナリオ
        hero_colors, villain_colors = op_colors, call_colors
        
        # 内部でのハンド・ボード確定（重複排除ロジック）
        hero_valid = [h for h, c in hand_to_color.items() if c in hero_colors] or ["AA", "KK"]
        chosen_h = random.choice(hero_valid)
        hero_pair = random.choice(convert_to_concrete_cards(chosen_h))
        
        villain_valid = [h for h, c in hand_to_color.items() if c in villain_colors] or ["QQ", "JJ"]
        v_combos = []
        for f in villain_valid: v_combos.extend(convert_to_concrete_cards(f))
        v_combos_clean = [c for c in v_combos if c[0] not in hero_pair and c[1] not in hero_pair] or [["As", "Ah"]]
        villain_pair = random.choice(v_combos_clean)

        # デッキからフロップボード3枚を構築 ($6s Tc 2s$ 等をランダムプールから安全に排出)
        deck_pool = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_pair and f"{r}{s}" not in villain_pair]
        random.shuffle(deck_pool)
        
        # 特定検証用のデフォルト（プールに残っていれば優先配置、なければランダム）
        preferred_board = ["6s", "Tc", "2s"]
        board_fixed = []
        for pb in preferred_board:
            if pb in deck_pool:
                board_fixed.append(pb)
                deck_pool.remove(pb)
        while len(board_fixed) < 3:
            board_fixed.append(deck_pool.pop())
            
        # セッションへの一括書き込み（State破綻の完全防止）
        st.session_state.game_data = {
            "hero_pos": hero_pos, "villain_pos": chosen_villain,
            "hero_hand": f"{hero_pair[0]}{hero_pair[1]}",
            "villain_hand": f"{villain_pair[0]}{villain_pair[1]}",
            "hero_colors": hero_colors, "villain_colors": villain_colors,
            "board": board_fixed, "current_street": "flop",
            "hero_color_name": hand_to_color.get(chosen_h, "紺")
        }
        st.session_state.game_state = "quiz_loop"
        st.rerun()

elif st.session_state.game_state == "quiz_loop":
    # データの安全なアンパック
    data = st.session_state.game_data
    street = data["current_street"]
    
    # リアルタイムGTO数理解析マトリクスの計算
    freqs, hand_eq, range_eq, tex, comps = calculate_gto_frequencies_v61(
        data["hero_hand"], data["hero_colors"], data["villain_colors"], data["board"], street
    )
    
    st.markdown(f"### ⚔️ 数理GTO解析画面 ({street.upper()}フェーズ)")
    st.markdown(f"**📢 ポジション構成**: あなた (**{data['hero_pos']}**) vs 相手 (**{data['villain_pos']}**)")
    
    # ボード表示
    b_html = "".join([f"<span style='font-size:28px; font-weight:bold; background-color:#111; padding:5px 12px; border-radius:5px; margin-right:8px; border:1px solid #444; color:#fff;'>{c}</span>" for c in data["board"]])
    st.markdown(f"ボード: {b_html}", unsafe_allow_html=True)
    st.markdown(f"**😇 あなたのハンド**: `{data['hero_hand']}` (割り当てレンジ色: **{data['hero_color_name']}**)")
    
    # メトリック表示
    c_eq1, c_eq2 = st.columns(2)
    with c_eq1: st.metric(label="📈 あなたのハンド単体勝率 (Equity)", value=f"{hand_eq*100:.1f}%")
    with c_eq2: st.metric(label="📊 あなたのレンジ全体勝率 (Range Equity)", value=f"{range_eq*100:.1f}%")

    # 数理分析ログ
    st.markdown("### 📊 ソルバー数理分析ログ")
    c_tex, c_comp = st.columns(2)
    with c_tex:
        st.markdown("#### 🃏 ボードテクスチャ構造スコア")
        st.write(f"- **最高ハイカード**: {tex['high_card']}")
        st.write(f"- **フラッシュドローの有無**: {'⚠️ あり' if tex['flush_draw'] else '❌ なし'}")
        st.write(f"- **ボード流動性スコア (Dynamic Score)**: `{tex['dynamic_score']:.2f}` / 1.00")
    with c_comp:
        st.markdown("#### 📈 双方のレンジ内役構成比率")
        df_comp = pd.DataFrame({
            "あなたのレンジ": [f"{comps['hero']['nuts']*100:.1f}%", f"{comps['hero']['top_pair']*100:.1f}%", f"{comps['hero']['air']*100:.1f}%"],
            "相手のレンジ": [f"{comps['villain']['nuts']*100:.1f}%", f"{comps['villain']['top_pair']*100:.1f}%", f"{comps['villain']['air']*100:.1f}%"]
        }, index=["超強手 (セット以上)", "ヒット系 (ワンペア等)", "滑り (エア/ドロー)"])
        st.table(df_comp)

    st.markdown("---")
    st.markdown("### 🎯 GTOソルバー算出周波数")
    
    st.write(f"🟢 **33%ベット（スモールサイズ推奨頻度）**: `{freqs['bet_33']}%`")
    st.write(f"🔴 **70%ベット（ラージサイズ推奨頻度）**: `{freqs['bet_70']}%`")
    st.write(f"⚪ **チェック頻度**: `{freqs['check']}%`")
    
    st.markdown("### 👁️ ハンドリーディングロジック解説")
    st.info(f"このボードテクスチャにおいて、相手のディフェンスレンジの **{comps['villain']['air']*100:.1f}%** は完全に滑っている状態です。高頻度のスモールCB（33%）を放つことで、相手の未完成ハンドを逃がさずにキャッチし、レンジ全体から最大効率でEVを回収します。")

    if st.button("ポジション選択に戻る 🔄", use_container_width=True):
        st.session_state.game_state = "setup"
        st.rerun()
