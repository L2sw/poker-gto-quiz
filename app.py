import streamlit as st
import pandas as pd
import eval7
import random

# 画面設定
st.set_page_config(page_title="GTO Training Interactive", page_icon="🃏", layout="wide")

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

def calculate_gto_frequencies_v62(active_hand_str, active_colors, passive_colors, board_cards, street):
    """手番プレイヤー側の視点でGTO推奨頻度を動的計算"""
    h_range = get_range_combos(active_colors, hand_to_color)
    v_range = get_range_combos(passive_colors, hand_to_color)
    board_obj = [eval7.Card(c) for c in board_cards]
    
    act_hand = [active_hand_str[:2], active_hand_str[2:]]
    hand_eq = run_simulation([act_hand], v_range, board_obj, iterations=300)
    range_eq = run_simulation(h_range, v_range, board_obj, iterations=300)
    
    texture = analyze_board_texture(board_cards)
    h_comp = calculate_range_composition(h_range, board_cards)
    v_comp = calculate_range_composition(v_range, board_cards)
    
    freq = {"bet_70": 0.0, "bet_33": 0.0, "check": 0.0}
    
    if street in ["turn", "river"]:
        if hand_eq >= 0.70: freq["bet_70"], freq["bet_33"], freq["check"] = 65.0, 15.0, 20.0
        elif hand_eq >= 0.52: freq["bet_70"], freq["bet_33"], freq["check"] = 10.0, 60.0, 30.0
        else: freq["bet_70"], freq["bet_33"], freq["check"] = 0.0, 10.0, 90.0
    else:
        # フロップ数理決定
        if range_eq >= 0.54:
            if texture["values"][0] <= 11:
                freq["bet_33"] = round(85.0 * (1.0 - texture["dynamic_score"] * 0.1), 1)
                freq["bet_70"] = round(5.0 + (texture["dynamic_score"] * 10.0), 1)
            else:
                freq["bet_70"] = round(45.0 * (h_comp["nuts"] / (v_comp["nuts"] + 0.01)), 1)
                freq["bet_33"] = round(45.0, 1)
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

def judge_defense_gto_action(hand_eq, bet_pct):
    mdf = 1.0 / (1.0 + bet_pct)
    if hand_eq >= 0.75: return "raise", {"fold": 0.0, "call": 30.0, "raise": 70.0}
    elif hand_eq >= 0.50: return "call", {"fold": 0.0, "call": 85.0, "raise": 15.0}
    elif hand_eq >= (1.0 - mdf) * 0.80: return "call", {"fold": 10.0, "call": 90.0, "raise": 0.0}
    else: return "fold", {"fold": 100.0, "call": 0.0, "raise": 0.0}

# --- 3. メインアプリ制御 ---
if "game_state" not in st.session_state: st.session_state.game_state = "setup"

if st.session_state.game_state == "setup":
    st.markdown("### 🧬 GTO 実戦ストリート連続トレーニング")
    hero_pos = st.selectbox("あなたのポジション (Hero)", PREFLOP_ORDER, index=0) # UTG
    villain_pos_option = st.selectbox("相手のポジション (Villain)", ["ランダムに決定"] + PREFLOP_ORDER)
    
    if st.button("ゲームスタート 🚀", use_container_width=True):
        if villain_pos_option == "ランダムに決定":
            available_p = [p for p in PREFLOP_ORDER if p != hero_pos]
            chosen_villain = random.choice(available_p)
        else:
            chosen_villain = villain_pos_option

        # ポジションの前後関係の特定 (OOP vs IP)
        hero_oop = POSTFLOP_ORDER.index(hero_pos) < POSTFLOP_ORDER.index(chosen_villain)
        
        # あなたがオープンレイズし、相手がコールしたシチュエーションを構築
        op_colors, call_colors = get_preflop_ranges(hero_pos, chosen_villain)
        hero_colors, villain_colors = op_colors, call_colors
        
        # 固有コンボの自動生成（KsKcなどのプレミアムをあなたへ、ミドル系を相手へ、かつ重複を完全排除）
        hero_valid = ["KsKc", "AhAs", "QhQd", "KhQh", "AsKs"]
        chosen_h = random.choice(hero_valid)
        hero_pair = [chosen_h[:2], chosen_h[2:]]
        
        villain_valid = ["JsTs", "9s8s", "JhTh", "QdJd", "8h7h"]
        chosen_v = random.choice(villain_valid)
        villain_pair = [chosen_v[:2], chosen_v[2:]]
        
        # デッキから検証に最適なボード（6s Tc 2sなど）を優先してドロップさせる安全ロジック
        deck_pool = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_pair and f"{r}{s}" not in villain_pair]
        random.shuffle(deck_pool)
        
        preferred_board = ["6s", "Tc", "2s"]
        board_fixed = []
        for pb in preferred_board:
            if pb in deck_pool:
                board_fixed.append(pb)
                deck_pool.remove(pb)
        while len(board_fixed) < 3:
            board_fixed.append(deck_pool.pop())

        st.session_state.game_data = {
            "hero_pos": hero_pos, "villain_pos": chosen_villain, "hero_oop": hero_oop,
            "hero_hand": f"{hero_pair[0]}{hero_pair[1]}", "villain_hand": f"{villain_pair[0]}{villain_pair[1]}",
            "hero_colors": hero_colors, "villain_colors": villain_colors,
            "board": board_fixed, "deck": deck_pool, "pot": 6.0, "current_street": "flop", "sub_phase": "action"
        }
        st.session_state.game_state = "quiz_loop"
        st.session_state.action_feedback = ""
        st.rerun()

elif st.session_state.game_state == "quiz_loop":
    data = st.session_state.game_data
    street = data["current_street"]
    hero_oop = data["hero_oop"]
    
    st.markdown(f"### ⚔️ 実戦 GTO トレーニング: {street.upper()} (ポット: {data['pot']:.1f}bb)")
    st.caption(f"🛡️ あなた: **{data['hero_pos']}** (OOP)  vs  🤖 相手: **{data['villain_pos']}** (IP)" if hero_oop else f"🛡️ 相手: **{data['villain_pos']}** (OOP)  vs  🤖 あなた: **{data['hero_pos']}** (IP)")
    
    b_html = "".join([f"<span style='font-size:28px; font-weight:bold; background-color:#111; padding:5px 12px; border-radius:5px; margin-right:8px; border:1px solid #444; color:#fff;'>{c}</span>" for c in data["board"]])
    st.markdown(f"ボード: {b_html}", unsafe_allow_html=True)
    st.markdown(f"**😇 あなたのハンド**: `{data['hero_hand']}`")

    # 現在の手番プレイヤーのGTO計算
    if data["sub_phase"] == "action":
        # 先攻番のアクション選択
        if hero_oop:
            # --- 【手番：あなた (OOP)】 ---
            freqs, h_eq, r_eq, tex, comps = calculate_gto_frequencies_v62(data["hero_hand"], data["hero_colors"], data["villain_colors"], data["board"], street)
            
            # 最善アクション（最高頻度）の自動決定
            best_action_str = max(freqs, key=freqs.get)
            
            st.markdown("#### 👉 あなた（OOP）のアクション番です。GTO最善手を選んでください")
            st.write(f"💡 (ソルバー内部計算値 -> 33%Bet: `{freqs['bet_33']}%` | 70%Bet: `{freqs['bet_70']}%` | Check: `{freqs['check']}%`) ")
            
            ans = st.radio("あなたのアクション:", ["33%ベット (スモール)", "70%ベット (ラージ)", "チェック"], key=f"act_{street}")
            
            if st.button("アクションを確定", use_container_width=True):
                user_act_mapped = "bet_33" if "33%" in ans else ("bet_70" if "70%" in ans else "check")
                
                if user_act_mapped == best_action_str:
                    st.session_state.action_feedback = f"🟢 **正解！最善手です。** ソルバー推奨の {ans} を選択しました。"
                    # 次のフェーズへ進行（自分が打ったなら相手の防衛、自分がチェックなら相手のアクション）
                    if user_act_mapped == "check":
                        data["sub_phase"] = "villain_action"
                    else:
                        data["sub_phase"] = "villain_defense"
                        data["last_bet_pct"] = 0.33 if user_act_mapped == "bet_33" else 0.70
                else:
                    st.session_state.action_feedback = f"❌ **GTO乖離！** あなたは {ans} を選びましたが、このシーンの最善最高頻度は `{best_action_str}` です。最善手を選び直すか、このまま進んでください。"
                st.rerun()
        else:
            # --- 【手番：相手 (OOP) の自動最善アクション】 ---
            v_freqs, v_h_eq, v_r_eq, _, _ = calculate_gto_frequencies_v62(data["villain_hand"], data["villain_colors"], data["hero_colors"], data["board"], street)
            v_best = max(v_freqs, key=v_freqs.get)
            
            st.info(f"🤖 相手 ({data['villain_pos']}) が思考中...")
            if v_best == "check":
                st.success("🤖 相手は GTO最善手である「チェック」を選択しました。")
                data["sub_phase"] = "hero_action" # あなた（IP）のアクション番へ
            else:
                pct = 0.33 if v_best == "bet_33" else 0.70
                st.warning(f"💥 相手は GTO最善手である「{int(pct*100)}% ベット」を仕掛けてきました！")
                data["sub_phase"] = "hero_defense" # あなた（IP）の防衛番へ
                data["last_bet_pct"] = pct
            st.button("次へ進む ➡️")
            st.stop()

    # 防衛フェーズやその他のアクション分岐
    elif data["sub_phase"] == "villain_action":
        # あなたがチェックした後の、相手（IP）のアクション番
        v_freqs, _, _, _, _ = calculate_gto_frequencies_v62(data["villain_hand"], data["villain_colors"], data["hero_colors"], data["board"], street)
        v_best = max(v_freqs, key=v_freqs.get)
        if v_best == "check":
            st.success("🤖 相手も最善手「チェックバック」を選択。このストリートは終了です。")
            data["sub_phase"] = "next_street_trigger"
        else:
            pct = 0.33 if v_best == "bet_33" else 0.70
            st.warning(f"💥 相手はチェックに対して「{int(pct*100)}% ベット」を打ってきました。")
            data["sub_phase"] = "hero_defense"
            data["last_bet_pct"] = pct
        st.button("次へ進む ➡️")
        st.stop()

    elif data["sub_phase"] == "villain_defense":
        # あなたがベットした後の、相手（IP）のGTO防衛
        v_range = get_range_combos(data["villain_colors"], hand_to_color)
        board_obj = [eval7.Card(c) for c in data["board"]]
        v_hand_eq = run_simulation([[data["villain_hand"][:2], data["villain_hand"][2:]]], get_range_combos(data["hero_colors"], hand_to_color), board_obj)
        v_best_def, _ = judge_defense_gto_action(v_hand_eq, data["last_bet_pct"])
        
        if v_best_def == "fold":
            st.success("🤖 相手はGTOに基づき「フォールド」を選択しました。あなたの勝利です！")
            st.session_state.game_state = "setup"
        elif v_best_def == "call":
            st.info("🤖 相手はGTOに基づき「コール」しました。ポットが拡大し、次のストリートへ進みます。")
            data["pot"] += (data["pot"] * data["last_bet_pct"] * 2)
            data["sub_phase"] = "next_street_trigger"
        else:
            st.warning("🤖 相手はGTOに基づき「レイズ」を選択しました！(このトレーニング版ではコール扱いとして次へ進みます)")
            data["pot"] += (data["pot"] * data["last_bet_pct"] * 3)
            data["sub_phase"] = "next_street_trigger"
        st.button("次へ進む ➡️")
        st.stop()

    elif data["sub_phase"] == "hero_action":
        # 相手がチェックした後の、あなた（IP）のアクション番
        freqs, h_eq, r_eq, _, _ = calculate_gto_frequencies_v62(data["hero_hand"], data["hero_colors"], data["villain_colors"], data["board"], street)
        best_action_str = max(freqs, key=freqs.get)
        
        st.markdown("#### 👉 あなた（IP）のアクション番です。")
        ans = st.radio("あなたのアクション:", ["33%ベット (スモール)", "70%ベット (ラージ)", "チェックバック"], key=f"act_ip_{street}")
        if st.button("アクションを確定", use_container_width=True):
            user_act_mapped = "bet_33" if "33%" in ans else ("bet_70" if "70%" in ans else "check")
            if user_act_mapped == best_action_str:
                st.session_state.action_feedback = "🟢 **正解！最善手です。**"
                if user_act_mapped == "check":
                    data["sub_phase"] = "next_street_trigger"
                else:
                    data["sub_phase"] = "villain_defense"
                    data["last_bet_pct"] = 0.33 if user_act_mapped == "bet_33" else 0.70
            else:
                st.session_state.action_feedback = f"❌ **GTO乖離！** 最善手は `{best_action_str}` です。"
            st.rerun()

    elif data["sub_phase"] == "hero_defense":
        # 相手がベットしてきた時の、あなた（Hero）の防衛番
        board_obj = [eval7.Card(c) for c in data["board"]]
        h_hand_eq = run_simulation([[data["hero_hand"][:2], data["hero_hand"][2:]]], get_range_combos(data["villain_colors"], hand_to_color), board_obj)
        best_def, def_freqs = judge_defense_gto_action(h_hand_eq, data["last_bet_pct"])
        
        st.markdown(f"#### 🛡️ あなたの防衛番です (相手のベットサイズ: {int(data['last_bet_pct']*100)}%)")
        st.write(f"💡 (推奨 -> Fold: `{def_freqs['fold']}%` | Call: `{def_freqs['call']}%` | Raise: `{def_freqs['raise']}%`) ")
        
        ans_def = st.radio("防衛アクションを選択:", ["フォールド", "コール", "レイズ"], key=f"def_{street}")
        if st.button("防衛を確定", use_container_width=True):
            user_def_mapped = "fold" if "フォールド" in ans_def else ("call" if "コール" in ans_def else "raise")
            if user_def_mapped == best_def:
                st.session_state.action_feedback = "🟢 **正解！最善の防衛アクションです。**"
                if user_def_mapped == "fold":
                    st.error("あなたをフォールドさせました。ゲーム終了です。")
                    st.session_state.game_state = "setup"
                else:
                    data["pot"] += (data["pot"] * data["last_bet_pct"] * 2)
                    data["sub_phase"] = "next_street_trigger"
            else:
                st.session_state.action_feedback = f"❌ **ディフェンス乖離！** このハンドのエクイティにおける最善手は `{best_def}` です。"
            st.rerun()

    # フィードバックの常時表示
    if st.session_state.action_feedback:
        st.info(st.session_state.action_feedback)

    # 次のストリートへのトリガー処理
    if data["sub_phase"] == "next_street_trigger":
        st.session_state.action_feedback = ""
        if street == "flop":
            data["current_street"] = "turn"
            data["board"].append(data["deck"].pop())
            data["sub_phase"] = "action"
        elif street == "turn":
            data["current_street"] = "river"
            data["board"].append(data["deck"].pop())
            data["sub_phase"] = "action"
        else:
            # リバーまで無事に終了 -> ショーダウン
            st.balloons()
            st.markdown("### 🏆 ショーダウン (ゲーム終了)")
            st.warning(f"🤖 相手の持っていたハンド: `{data['villain_hand']}`")
            board_obj = [eval7.Card(c) for c in data["board"]]
            h_scr = eval7.evaluate([eval7.Card(c) for c in [data['hero_hand'][:2], data['hero_hand'][2:]]] + board_obj)
            v_scr = eval7.evaluate([eval7.Card(c) for c in [data['villain_hand'][:2], data['villain_hand'][2:]]] + board_obj)
            
            if h_scr > v_scr: st.success("🎉 あなたのハンドが勝っていました！")
            elif v_scr > h_scr: st.error("😢 相手のハンドの方が強かったです。")
            else: st.warning("🤝 チョップ（引き分け）です。")
            
            if st.button("次のトレーニングへ進む 🔄", use_container_width=True):
                st.session_state.game_state = "setup"
            st.stop()
        st.rerun()
