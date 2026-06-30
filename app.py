import streamlit as st
import random
import pandas as pd
import eval7
import copy

# 画面設定
st.set_page_config(page_title="GTO Precision Trainer v2", page_icon="🃏", layout="wide")

# --- 1. 色の階層定義（下が強く、上が弱い） ---
ALL_COLORS = ["グレー", "薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]

# 厳密なポジション順序（9人フルリングを基準に、残り人数を正確に割り出す）
PREFLOP_ORDER = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POSTFLOP_ORDER = ["SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO", "BTN"]

@st.cache_data
def load_ranges_from_csv(csv_path="poker_range_list.csv"):
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['hand'], df['color']))
    except:
        # フォールバック
        return {"AA": "紺", "AKs": "紺", "J9o": "グレー", "76s": "白"}

hand_to_color = load_ranges_from_csv()

# --- 📐 ルールに基づくレンジ算出エンジン ---
def get_open_min_color(pos):
    """ポジションから後ろの人数を正確に割り出し、オープン可能な最低の色を返す"""
    idx = PREFLOP_ORDER.index(pos)
    left_players = len(PREFLOP_ORDER) - 1 - idx  # 自分より後にアクションする人数
    
    if left_players == 2: return "グレー＋紫枠"     # SB
    elif left_players == 3: return "白"             # BTN
    elif left_players in [4, 5]: return "水色"       # CO, HJ
    elif left_players in [6, 7]: return "緑"         # LJ, UTG+1
    else: return "黄"                               # UTG (残り8人以上)

def get_preflop_ranges(opener_pos, defender_pos):
    """指定された2ポジション間のオープン・コール・3betレンジを厳密に計算"""
    op_min_color = get_open_min_color(opener_pos)
    op_min_idx = ALL_COLORS.index(op_min_color)
    
    opener_colors = ALL_COLORS[op_min_idx:]
    call_colors = []
    three_bet_colors = []
    
    if defender_pos == "BB":
        if opener_pos == "BTN":
            call_colors = ALL_COLORS[ALL_COLORS.index("薄ピンク"):]
        elif opener_pos == "CO":
            call_colors = ALL_COLORS[ALL_COLORS.index("グレー＋紫枠"):]
        else:
            call_colors = ALL_COLORS[ALL_COLORS.index("白"):]
        
        # BBの3ベットは相手の2個上以上
        three_bet_colors = ALL_COLORS[(op_min_idx + 2):]
    else:
        # 原則ルール
        if op_min_idx + 1 < len(ALL_COLORS):
            call_colors = [ALL_COLORS[op_min_idx + 1]]
        if op_min_idx + 2 < len(ALL_COLORS):
            three_bet_colors = ALL_COLORS[(op_min_idx + 2):]

    return opener_colors, call_colors, three_bet_colors

# --- 2. カード生成とシミュレーション補助関数 ---
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

def run_simulation(hero_combos, villain_combos, board, iterations=700):
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

# --- 3. GTO意思決定マトリクス ---
def calculate_gto_frequencies(hand_eq, range_eq, street):
    freq = {"bet_70": 0.0, "bet_33": 0.0, "check": 0.0}
    # レンジ有利度によるベースライン調整
    if range_eq >= 0.54:   small, large, chk = 50, 20, 30
    elif range_eq <= 0.46: small, large, chk = 10, 5, 85
    else:                  small, large, chk = 30, 15, 55

    if hand_eq >= 0.75:
        freq["bet_70"], freq["bet_33"], freq["check"] = 65.0, 20.0, 15.0
    elif hand_eq >= 0.55:
        freq["bet_70"], freq["bet_33"], freq["check"] = 5.0, 45.0, 50.0
    elif 0.35 <= hand_eq < 0.55:
        freq["bet_70"], freq["bet_33"], freq["check"] = (25.0, 35.0, 40.0) if range_eq >= 0.50 else (5.0, 15.0, 80.0)
    else:
        freq["bet_70"], freq["bet_33"], freq["check"] = (15.0, 20.0, 65.0) if range_eq >= 0.54 and street != "river" else (0.0, 5.0, 95.0)
    return freq

def judge_defense_gto_action(hand_eq, bet_pct):
    """相手のベットサイズ(bet_pct)に対する、GTOのディフェンス（フォールド含む）頻度"""
    mdf = 1.0 / (1.0 + bet_pct)  # 最低防衛頻度 (Minimum Defense Frequency)
    # ハンド勝率がMDFの基準を大幅に下回る場合はフォールドが最善になる
    if hand_eq >= 0.78:   return {"fold": 0.0, "call": 40.0, "raise": 60.0}
    elif hand_eq >= 0.52: return {"fold": 0.0, "call": 85.0, "raise": 15.0}
    elif hand_eq >= (1.0 - mdf) * 0.85: return {"fold": 25.0, "call": 75.0, "raise": 0.0}
    elif hand_eq >= (1.0 - mdf) * 0.5:  return {"fold": 60.0, "call": 40.0, "raise": 0.0}
    else:                 return {"fold": 100.0, "call": 0.0, "raise": 0.0}

def generate_advanced_gto_explanation(mode, action_idx, freq_dict, hand_eq, range_eq, data, street):
    action_map = {1: "bet_33", 2: "bet_70", 3: "check"} if "アクション" in mode else {1: "fold", 2: "call", 3: "raise"}
    chosen_key = action_map[action_idx]
    chosen_freq = freq_dict.get(chosen_key, 0.0)
    
    if chosen_freq >= 30.0:
        eval_text = "🟩 **【最善手 / 推奨】** GTO戦略に完全に合致しています。EVが最も高いアクションです。"
    elif chosen_freq > 0.0:
        eval_text = "🟨 **【許容手 / 混合戦略】** 選択肢として存在しますが、頻度は低めです。"
    else:
        eval_text = "🟥 **【悪手（ブラダー）】** レンジバランスを崩すか、大幅にEVをロスする選択です。"

    return f"""
### 📊 【詳細解析フィードバック】
{eval_text}

#### 🤖 ソルバーの推奨頻度マトリクス
- ⚪ **チェック / フォールド**: `{freq_dict.get('check', freq_dict.get('fold', 0.0)):.1f}%`
- 🟢 **33%ベット / コール**: `{freq_dict.get('bet_33', freq_dict.get('call', 0.0)):.1f}%`
- 🔴 **70%ベット / レイズ**: `{freq_dict.get('bet_70', freq_dict.get('raise', 0.0)):.1f}%`
"""

# --- 4. ゲーム管理ロジック ---
if "game_state" not in st.session_state: st.session_state.game_state = "setup"
if "quiz_phase" not in st.session_state: st.session_state.quiz_phase = 1
if "quiz_answered" not in st.session_state: st.session_state.quiz_answered = False
if "villain_bet_size" not in st.session_state: st.session_state.villain_bet_size = 0.0

if st.session_state.game_state == "setup":
    st.markdown("### 🃏 GTO ポジション＆レンジ完全シミュレーター (検証済マトリクス版)")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        hero_pos_select = st.selectbox("あなたのポジション", ["ランダム"] + PREFLOP_ORDER)
    with col_s2:
        situation_select = st.selectbox("シチュエーション", ["ランダム", "自分がオープンレイズした側", "相手がオープンレイズして自分がコールした側"])

    if st.button("シチュエーションを生成して開始 🚀", use_container_width=True):
        all_p = PREFLOP_ORDER.copy()
        hero_pos = random.choice(all_p) if hero_pos_select == "ランダム" else hero_pos_select
        all_p.remove(hero_pos)
        villain_pos = random.choice(all_p)
        
        h_idx = PREFLOP_ORDER.index(hero_pos)
        v_idx = PREFLOP_ORDER.index(villain_pos)
        
        if situation_select == "自分がオープンレイズした側":
            opener, defender = hero_pos, villain_pos
        elif situation_select == "相手がオープンレイズして自分がコールした側":
            opener, defender = villain_pos, hero_pos
        else:
            if h_idx < v_idx: opener, defender = hero_pos, villain_pos
            else: opener, defender = villain_pos, hero_pos

        op_colors, call_colors, _ = get_preflop_ranges(opener, defender)
        
        if hero_pos == opener:
            hero_colors, villain_colors = op_colors, call_colors
            summary = f"あなた ({hero_pos}) のオープンレイズに、相手 ({villain_pos}) がルール通りコールしました。"
            v_action_type = "コール"
        else:
            hero_colors, villain_colors = call_colors, op_colors
            summary = f"相手 ({villain_pos}) のオープンレイズに、あなた ({hero_pos}) がルール通りコールしました。"
            v_action_type = f"オープン (最低色: {get_open_min_color(villain_pos)})"

        hero_valid = [h for h, c in hand_to_color.items() if c in hero_colors]
        if not hero_valid: hero_valid = ["AA", "KK"]
        chosen_h = random.choice(hero_valid)
        hero_pair = random.choice(convert_to_concrete_cards(chosen_h))
        
        villain_valid = [h for h, c in hand_to_color.items() if c in villain_colors]
        if not villain_valid: villain_valid = ["QQ", "JJ"]
        v_combos = []
        for f in villain_valid: v_combos.extend(convert_to_concrete_cards(f))
        v_combos_clean = [c for c in v_combos if c[0] not in hero_pair and c[1] not in hero_pair]
        if not v_combos_clean: v_combos_clean = [["As", "Ah"]]
        villain_pair = random.choice(v_combos_clean)

        deck = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_pair and f"{r}{s}" not in villain_pair]
        random.shuffle(deck)
        
        st.session_state.game_data = {
            "hero_pos": hero_pos, "villain_pos": villain_pos,
            "hero_hand_raw": f"{hero_pair[0]}{hero_pair[1]}", "hero_color": hand_to_color.get(chosen_h),
            "villain_hand_raw": f"{villain_pair[0]}{villain_pair[1]}",
            "hero_colors": hero_colors, "villain_colors": villain_colors,
            "v_action_type": v_action_type, "preflop_summary": summary,
            "deck": deck, "board": [], "pot": 6.0, "current_street": "flop"
        }
        st.session_state.game_state = "quiz_loop"
        st.session_state.quiz_phase = 1
        st.session_state.quiz_answered = False
        st.rerun()

elif st.session_state.game_state == "quiz_loop":
    data = st.session_state.game_data
    street = data["current_street"]
    # ポストフロップの順番割り出し (OOP=先攻か判定)
    hero_oop = POSTFLOP_ORDER.index(data["hero_pos"]) < POSTFLOP_ORDER.index(data["villain_pos"])
    
    if len(data["board"]) == 0 and street == "flop": data["board"] = [data["deck"].pop() for _ in range(3)]
    elif len(data["board"]) == 3 and street == "turn": data["board"].append(data["deck"].pop())
    elif len(data["board"]) == 4 and street == "river": data["board"].append(data["deck"].pop())
    
    st.markdown(f"### ⚔️ {street.upper()} フェーズ (ポット: {data['pot']:.1f}bb)")
    st.info(f"📢 プリフロップ状況: {data['preflop_summary']}")
    
    b_html = "".join([f"<span style='font-size:30px; font-weight:bold; background-color:#222; padding:5px 10px; border-radius:5px; margin-right:8px; border:1px solid #555;'>{c}</span>" for c in data["board"]])
    st.markdown(f"ボード: {b_html}", unsafe_allow_html=True)
    st.markdown(f"**😇 あなた ({data['hero_pos']})**: `{data['hero_hand_raw']}` (判定色: {data['hero_color']}) | **🤖 相手 ({data['villain_pos']})**: `[??]`")

    # シミュレーションによる正確な勝率計算
    h_range = get_range_combos(data["hero_colors"], hand_to_color)
    v_range = get_range_combos(data["villain_colors"], hand_to_color)
    board_obj = [eval7.Card(c) for c in data["board"]]
    
    hand_eq = run_simulation([[data["hero_hand_raw"][:2], data["hero_hand_raw"][2:]]], v_range, board_obj)
    range_eq = run_simulation(h_range, v_range, board_obj)
    v_hand_eq = run_simulation([[data["villain_hand_raw"][:2], data["villain_hand_raw"][2:]]], h_range, board_obj)
    
    gto_freqs = calculate_gto_frequencies(hand_eq, range_eq, street)
    
    st.markdown("---")

    # --- 🕹️ アクション進行部（フォールドの組み込み） ---
    if hero_oop:
        # Heroが先攻(OOP)の場合
        if st.session_state.quiz_phase == 1:
            st.write("👉 あなた（OOP）のアクション番です。ベットして攻めるか、チェックして様子を見ますか？")
            ans = st.radio("選択:", ["1: 33%ベット", "2: 70%ベット", "3: チェック"], key=f"act_{street}")
            choice = int(ans[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    st.session_state.quiz_answered = True
                    st.rerun()
            else:
                st.markdown(generate_advanced_gto_explanation("アクション", choice, gto_freqs, hand_eq, range_eq, data, street))
                if st.button("次へ進む ➡️"):
                    st.session_state.quiz_answered = False
                    if choice in [1, 2]:
                        # Heroのベットに対する相手のディフェンス
                        pct = 0.33 if choice == 1 else 0.70
                        v_def = judge_defense_gto_action(v_hand_eq, pct)
                        v_roll = random.uniform(0, 100)
                        if v_roll < v_def["fold"]:
                            st.success("相手はフォールドしました！あなたの勝ちです。")
                            st.session_state.game_state = "setup"
                        else:
                            data["pot"] += (data["pot"] * pct * 2)
                            st.session_state.quiz_phase = "next_trigger"
                    else:
                        # Heroチェック後の相手のアクション
                        st.session_state.quiz_phase = 2
                    st.rerun()
                    
        elif st.session_state.quiz_phase == 2:
            # Heroがチェックした後、相手(IP)がベットしてきたシチュエーション
            v_gto = calculate_gto_frequencies(v_hand_eq, 1.0 - range_eq, street)
            v_roll = random.uniform(0, 100)
            v_pct = 0.70 if v_roll < v_gto["bet_70"] else (0.33 if v_roll < (v_gto["bet_70"] + v_gto["bet_33"]) else 0.0)
            
            if v_pct == 0.0:
                st.info("🤖 相手はチェックバックしました。")
                if st.button("次のストリートへ進む ➡️"):
                    st.session_state.quiz_phase = "next_trigger"
                    st.rerun()
            else:
                st.warning(f"💥 相手が {int(v_pct*100)}% ベットを仕掛けてきました！【フォールド】の選択肢が発生しています。")
                h_def = judge_defense_gto_action(hand_eq, v_pct)
                ans_def = st.radio("あなたの対応:", ["1: フォールド", "2: コール", "3: レイズ"], key=f"def_{street}")
                choice_def = int(ans_def[0])
                
                if not st.session_state.quiz_answered:
                    if st.button("ディフェンスを確定する", use_container_width=True):
                        st.session_state.quiz_answered = True
                        st.rerun()
                else:
                    st.markdown(generate_advanced_gto_explanation("防衛", choice_def, h_def, hand_eq, range_eq, data, street))
                    if st.button("結果を確定して進む ➡️"):
                        st.session_state.quiz_answered = False
                        if choice_def == 1:
                            st.error("フォールドしました。このハンドを降ります。")
                            st.session_state.game_state = "setup"
                        else:
                            if choice_def == 2: data["pot"] += (data["pot"] * v_pct * 2)
                            st.session_state.quiz_phase = "next_trigger"
                        st.rerun()
    else:
        # Heroが後攻(IP)の場合
        # 相手(OOP)がチェックしたかベットしたかを先にシミュレート
        v_gto = calculate_gto_frequencies(v_hand_eq, 1.0 - range_eq, street)
        v_roll = random.uniform(0, 100)
        v_pct = 0.70 if v_roll < v_gto["bet_70"] else (0.33 if v_roll < (v_gto["bet_70"] + v_gto["bet_33"]) else 0.0)
        
        if v_pct > 0.0:
            st.warning(f"💥 先攻の相手がドンク/Cベット ({int(v_pct*100)}%) を打ってきました！")
            h_def = judge_defense_gto_action(hand_eq, v_pct)
            ans_ip_def = st.radio("あなたの対応:", ["1: フォールド", "2: コール", "3: レイズ"], key=f"ip_def_{street}")
            choice_ip_def = int(ans_ip_def[0])
            
            if not st.session_state.quiz_answered:
                if st.button("ディフェンスを確定する", use_container_width=True):
                    st.session_state.quiz_answered = True
                    st.rerun()
            else:
                st.markdown(generate_advanced_gto_explanation("防衛", choice_ip_def, h_def, hand_eq, range_eq, data, street))
                if st.button("結果を確定して進む ➡️"):
                    st.session_state.quiz_answered = False
                    if choice_ip_def == 1:
                        st.error("フォールドしました。")
                        st.session_state.game_state = "setup"
                    else:
                        if choice_ip_def == 2: data["pot"] += (data["pot"] * v_pct * 2)
                        st.session_state.quiz_phase = "next_trigger"
                    st.rerun()
        else:
            st.success("🤖 相手はチェックしました。あなたのアクション番です。")
            ans_ip = st.radio("選択:", ["1: 33%ベット", "2: 70%ベット", "3: チェックバック"], key=f"ip_act_{street}")
            choice_ip = int(ans_ip[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    st.session_state.quiz_answered = True
                    st.rerun()
            else:
                st.markdown(generate_advanced_gto_explanation("アクション", choice_ip, gto_freqs, hand_eq, range_eq, data, street))
                if st.button("次へ進む ➡️"):
                    st.session_state.quiz_answered = False
                    if choice_ip in [1, 2]:
                        pct = 0.33 if choice_ip == 1 else 0.70
                        v_def = judge_defense_gto_action(v_hand_eq, pct)
                        if random.uniform(0, 100) < v_def["fold"]:
                            st.success("相手はフォールドしました！あなたの勝ちです。")
                            st.session_state.game_state = "setup"
                        else:
                            data["pot"] += (data["pot"] * pct * 2)
                            st.session_state.quiz_phase = "next_trigger"
                    else:
                        st.session_state.quiz_phase = "next_trigger"
                    st.rerun()

    # ストリート更新トリガー
    if st.session_state.quiz_phase == "next_trigger":
        if street == "flop": data["current_street"] = "turn"
        elif street == "turn": data["current_street"] = "river"
        else:
            st.balloons()
            st.markdown("### 🏆 ショーダウン結果")
            st.info(f"🔍 相手のハンド: 【 {data['villain_hand_raw']} 】")
            h_scr = eval7.evaluate([eval7.Card(c) for c in [data['hero_hand_raw'][:2], data['hero_hand_raw'][2:]]] + board_obj)
            v_scr = eval7.evaluate([eval7.Card(c) for c in [data['villain_hand_raw'][:2], data['villain_hand_raw'][2:]]] + board_obj)
            if h_scr > v_scr: st.success("あなたの勝ちです！")
            elif v_scr > h_scr: st.error("相手の勝ちです。")
            else: st.warning("チョップ（引き分け）です。")
            if st.button("新しいゲームを始める 🔄", use_container_width=True): st.session_state.game_state = "setup"
            st.stop()
        st.session_state.quiz_phase = 1
        st.rerun()
