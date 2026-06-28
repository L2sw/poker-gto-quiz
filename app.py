import streamlit as st
import random
import pandas as pd
import eval7
import copy

st.set_page_config(page_title="GTO特訓ツール（ポジション完全整合版）", page_icon="🃏", layout="centered")

# 1. 厳密なカラーの強さ階層
ALL_COLORS = ["薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]

# 2. 正しい人数カウントに基づくオープン最低カラー定義
POSITION_OPEN_MIN_COLOR = {
    "UTG": "黄",
    "LJ":  "緑",
    "HJ":  "水色",
    "CO":  "白",
    "BTN": "グレー＋紫枠",
}

# 内部判定用の完全なポジション順（SBを人数カウントのために残す）
FULL_POSITIONS_ORDER = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]

# クイズで選ばれる対象ポジション（SBをここから完全に除外）
QUIZ_ELIGIBLE_POSITIONS = ["UTG", "LJ", "HJ", "CO", "BTN", "BB"]

@st.cache_data
def load_ranges_from_csv(csv_path="poker_range_list.csv"):
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['hand'], df['color']))
    except:
        return {"AA": "紺", "AKo": "赤", "AQs": "赤", "AhJh": "黄", "KhQh": "緑", "76s": "水色", "54s": "白"}

def convert_to_concrete_cards(hand_str):
    ranks = "23456789TJQKA"
    suits = "shcd"
    r1, r2 = hand_str[0], hand_str[1]
    is_suited, is_offsuit = hand_str.endswith('s'), hand_str.endswith('o')
    combos = []
    if r1 == r2:
        for i in range(4):
            for j in range(i + 1, 4): combos.append([r1 + suits[i], r2 + suits[j]])
    elif is_suited:
        for s in suits: combos.append([r1 + s, r2 + s])
    elif is_offsuit or (not is_suited and not is_offsuit):
        for s1 in suits:
            for s2 in suits:
                if s1 != s2: combos.append([r1 + s1, r2 + s2])
    return combos

def get_range_combos(target_colors, hand_to_color):
    all_combos = []
    for hand, color in hand_to_color.items():
        if color in target_colors: all_combos.extend(convert_to_concrete_cards(hand))
    return all_combos

def is_hero_oop(hero_pos, villain_pos):
    # フロップ以降の先攻後攻（BBが最先攻、以降UTG~BTNの順）
    order_postflop = ["BB", "UTG", "LJ", "HJ", "CO", "BTN"]
    return order_postflop.index(hero_pos) < order_postflop.index(villain_pos)

def run_simulation(hero_combos, villain_combos, board, iterations=7000):
    if not hero_combos or not villain_combos: return 0.5
    hero_wins, villain_wins, ties = 0, 0, 0
    actual_iterations = 0
    deck_base = [eval7.Card(f"{r}{s}") for r in "23456789TJQKA" for s in "shcd"]
    for _ in range(iterations):
        h_cards_raw = random.choice(hero_combos)
        v_cards_raw = random.choice(villain_combos)
        h_cards = [eval7.Card(c) for c in h_cards_raw]
        v_cards = [eval7.Card(c) for c in v_cards_raw]
        used_cards = set(h_cards + v_cards + board)
        if len(used_cards) != len(h_cards) + len(v_cards) + len(board): continue
        actual_iterations += 1
        remaining_deck = [c for c in deck_base if c not in used_cards]
        num_to_draw = 5 - len(board)
        interim_board = board + random.sample(remaining_deck, num_to_draw) if num_to_draw > 0 else board
        hero_score = eval7.evaluate(h_cards + interim_board)
        villain_score = eval7.evaluate(v_cards + interim_board)
        if hero_score > villain_score: hero_wins += 1
        elif villain_score > hero_score: villain_wins += 1
        else: ties += 1
    return (hero_wins + 0.5 * ties) / actual_iterations if actual_iterations > 0 else 0.0

def generate_deep_mathematical_explanation(mode, action_idx, best_idx, hand_eq, range_eq, pot, bet_size=0.0):
    eq_p = hand_eq * 100
    req_p = range_eq * 100
    odds_text = ""
    if bet_size > 0:
        required_eq = (bet_size / (pot + bet_size * 2)) * 100
        odds_text = f"\n\n**【数理オッズ計算】**\n相手のベットに対し、コールに必要なエキティ（必要勝率）は $$\\text{{必要勝率}} = \\frac{{\\text{{コール額}}}}{{\\text{{現在のポット}} + \\text{{コール額}} + \\text{{相手のベット額}}}} = {required_eq:.1f}\\%$$ です。あなたのハンド勝率は **{eq_p:.1f}%** であるため、この必要ラインを"
        if eq_p >= required_eq:
            odds_text += f" **上回っており(+$E[V]$)、数学的にコールが正当化** されます。"
        else:
            odds_text += f" **下回っており(-$E[V]$)、長期的にフォールドが絶対正義** となります。"

    return f"""
    #### 📊 プリフロップ厳密ロジックによる解説
    1. **プリフロップでの力関係：**
       * 相手ポジション（Villain）のオープン基準カラー（SBを含んだ正しい人数カウント）に対し、あなたの手札が「1個上（＝コール）」か「2個以上上（＝リレイズ）」の正当な参加レンジを保ってポストフロップに突入しています。
    2. **勝率解析（{eq_p:.1f}%）：**
       * あなたの特定のハンドが、相手のオープンレンジ全体に対して持っている現在のエキティです。
    """ + odds_text

hand_to_color = load_ranges_from_csv()

if "game_state" not in st.session_state:
    st.session_state.game_state = "setup"
if "quiz_phase" not in st.session_state:
    st.session_state.quiz_phase = 1 
if "quiz_answered" not in st.session_state:
    st.session_state.quiz_answered = False
if "history_stack" not in st.session_state:
    st.session_state.history_stack = []

def save_to_history():
    snapshot = {
        "game_data": copy.deepcopy(st.session_state.game_data),
        "quiz_phase": st.session_state.quiz_phase,
        "quiz_answered": st.session_state.quiz_answered,
        "is_correct": st.session_state.get("is_correct", False),
        "user_choice": st.session_state.get("user_choice", 1),
        "best_action": st.session_state.get("best_action", 3),
    }
    st.session_state.history_stack.append(snapshot)

def pop_history():
    if st.session_state.history_stack:
        prev = st.session_state.history_stack.pop()
        st.session_state.game_data = prev["game_data"]
        st.session_state.quiz_phase = prev["quiz_phase"]
        st.session_state.quiz_answered = prev["quiz_answered"]
        st.session_state.is_correct = prev["is_correct"]
        st.session_state.user_choice = prev["user_choice"]
        st.session_state.best_action = prev["best_action"]
        st.rerun()

st.title("🃏 GTO")

if st.session_state.game_state == "quiz_loop":
    col_back, col_space = st.columns([1, 4])
    with col_back:
        if st.button("↩️ 1手戻る", disabled=(len(st.session_state.history_stack) == 0), use_container_width=True):
            pop_history()

# --- 1. セットアップ画面 ---
if st.session_state.game_state == "setup":
    st.session_state.history_stack = []
    st.subheader("🛠️ トレーニング設定")
    pos_choice = st.selectbox(
        "練習したい自分のポジション(Hero)を選択してください:", 
        ["ランダム", "UTG", "LJ", "HJ", "CO", "BTN", "BB"],
        key="pos_select"
    )
    
    if st.button("ゲームに挑む 🚀", use_container_width=True, key="start_btn"):
        clean_choice = pos_choice.split(" ")[0]
        if clean_choice == "ランダム":
            hero_pos = random.choice(QUIZ_ELIGIBLE_POSITIONS)
        else:
            hero_pos = clean_choice
            
        # プリフロップにおける絶対的な位置関係（SBを含むリストでインデックスを比較）
        hero_idx_full = FULL_POSITIONS_ORDER.index(hero_pos)
        
        if hero_pos == "UTG":
            # HeroがUTGの場合は前に誰もいないのでBBを相手とする
            villain_pos = "BB"
            v_min_color = "白" 
            h_min_color = POSITION_OPEN_MIN_COLOR["UTG"]
            hero_allowed_colors = ALL_COLORS[ALL_COLORS.index(h_min_color):]
            villain_colors = ALL_COLORS[ALL_COLORS.index("白"):]
            preflop_summary = f"あなた({hero_pos})がオープンレイズし、{villain_pos}がコールしました。"
        else:
            # 前にいるプレイヤー（Villain）を、SBを除外した候補からランダム選出
            available_villains = [p for p in FULL_POSITIONS_ORDER[:hero_idx_full] if p in QUIZ_ELIGIBLE_POSITIONS]
            villain_pos = random.choice(available_villains)
            
            v_min_color = POSITION_OPEN_MIN_COLOR[villain_pos]
            v_min_idx = ALL_COLORS.index(v_min_color)
            
            villain_colors = ALL_COLORS[v_min_idx:]
            
            # 🔥 「いきなりフォールド」を100%防ぐフィルター
            # 相手のオープン基準より「1個上(コール)」または「2個以上上(リレイズ)」のみ
            hero_allowed_colors = ALL_COLORS[v_min_idx + 1:]
            preflop_summary = f"前にいる {villain_pos} がオープンレイズ（基準：{v_min_color}以上）しました。それに対し、あなた({hero_pos})はフォールド以外のハンドを選択して参戦しました。"

        valid_hand_formats = [h for h, c in hand_to_color.items() if c in hero_allowed_colors]
        if not valid_hand_formats:
            valid_hand_formats = ["AA", "KK", "QQ", "AKs"]
            
        chosen_hand_format = random.choice(valid_hand_formats)
        hero_hand_pair = random.choice(convert_to_concrete_cards(chosen_hand_format))
        hero_hand_raw = f"{hero_hand_pair[0]}{hero_hand_pair[1]}"
        hero_color = hand_to_color.get(chosen_hand_format, "紺")
        
        if villain_pos != "BB":
            v_idx = ALL_COLORS.index(POSITION_OPEN_MIN_COLOR[villain_pos])
            h_idx = ALL_COLORS.index(hero_color)
            if h_idx == v_idx + 1:
                pf_action_text = "【コール参戦】"
            else:
                pf_action_text = "【リレイズ（3ベット）参戦】"
        else:
            pf_action_text = "【オープンレイズ】"
            
        deck = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_hand_pair]
        random.shuffle(deck)
        
        st.session_state.game_data = {
            "hero_pos": hero_pos,
            "villain_pos": villain_pos,
            "hero_hand_raw": hero_hand_raw,
            "hero_color": hero_color,
            "villain_colors": villain_colors,
            "v_min_color": v_min_color,
            "preflop_summary": preflop_summary,
            "pf_action_text": pf_action_text,
            "deck": deck,
            "board": [],
            "pot": 6.5 if "リレイズ" in pf_action_text else 3.5,
            "street_history": {},
            "current_street": "flop",
            "oop_action_taken": None
        }
        st.session_state.game_state = "quiz_loop"
        st.session_state.quiz_phase = 1
        st.session_state.quiz_answered = False
        st.rerun()

# --- 2. クイズコア画面 ---
elif st.session_state.game_state == "quiz_loop":
    data = st.session_state.game_data
    street = data["current_street"]
    hero_oop = is_hero_oop(data["hero_pos"], data["villain_pos"])
    
    if street == "flop" and len(data["board"]) == 0:
        data["board"] = [data["deck"].pop() for _ in range(3)]
    elif street == "turn" and len(data["board"]) == 3:
        data["board"].append(data["deck"].pop())
    elif street == "river" and len(data["board"]) == 4:
        data["board"].append(data["deck"].pop())
        
    st.markdown(f"### ⚔️ 【クイズ】{street.upper()} (ポット: {data['pot']:.1f}bb)")
    st.caption(f"📝 **プリフロップ履歴**: {data['preflop_summary']} あなたの手札は {data['hero_color']} のため、プリフロップは {data['pf_action_text']} の状態です。")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**あなた (Hero)**: `{data['hero_pos']}` (【{data['hero_color']}】レンジ)")
            st.markdown(f"**手札**: `{data['hero_hand_raw']}` | ポジション: `{'先攻(OOP)' if hero_oop else '後攻(IP)'}`")
        with col2:
            st.markdown(f"**相手 (Villain)**: `{data['villain_pos']}`")
            st.markdown(f"**敵オープンレンジ**: 【{data['v_min_color']}】以上全員")
            
    st.info(f"📁 **現在のボード**: `{' '.join(data['board'])}`  |  💰 **ポット**: {data['pot']:.1f}bb")
    
    hero_single_combo = [[data['hero_hand_raw'][0:2], data['hero_hand_raw'][2:4]]]
    hero_range_combos = get_range_combos([data['hero_color']], hand_to_color)
    villain_range_combos = get_range_combos(data['villain_colors'], hand_to_color)
    board_obj = [eval7.Card(c) for c in data['board']]
    
    with st.spinner("🧠 リアルタイムGTO演算中..."):
        hand_eq = run_simulation(hero_single_combo, villain_range_combos, board_obj, iterations=7000)
        range_eq = run_simulation(hero_range_combos, villain_range_combos, board_obj, iterations=7000)
        
    c_eq1, c_eq2 = st.columns(2)
    c_eq1.metric(label="📊 あなたのハンド勝率", value=f"{hand_eq*100:.1f} %")
    c_eq2.metric(label="📈 レンジ全体の勝率", value=f"{range_eq*100:.1f} %")
    st.markdown("---")
    
    hero_bet_count = list(data["street_history"].values()).count("bet")
    barrel_count = list(data["street_history"].values()).count("villain_bet")
    
    if hero_oop:
        if st.session_state.quiz_phase == 1:
            st.write("⚠️ あなたは**【先攻(OOP)】**です。最初のアクションを決めてください。")
            if street == "river":
                best_act = 3 if (hand_eq >= 0.85 and hero_bet_count >= 1) else (3 if barrel_count > 0 else (2 if hand_eq >= 0.70 else (1 if hand_eq >= 0.58 else 3)))
            else:
                if hand_eq >= 0.68: best_act = 2 if (range_eq >= 0.52 and hand_eq < 0.85) else 1
                elif hand_eq >= 0.56: best_act = 1
                elif hand_eq < 0.33 and range_eq >= 0.53: best_act = 1
                else: best_act = 3
                
            options = ["1: 小さくベットする (ポットの33%)", "2: 大きくベットする (ポットの66%〜75%)", "3: チェックする"]
            ans = st.radio("👉 番号を選択してください:", options, key=f"oop_p1_{street}")
            choice = int(ans[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_oop_p1_{street}"):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_act)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_act
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success(f"✨ 【正解です！】最適アクション：{options[best_act-1]}")
                else: st.error(f"❌ 【不正解！】あなたの選択：{options[choice-1]} (GTO推奨：{options[best_act-1]})")
                
                with st.expander("📊 なぜこの勝率と正解になるの？ディープ数理解説を開く"):
                    st.markdown(generate_deep_mathematical_explanation("oop_p1", choice, best_act, hand_eq, range_eq, data["pot"]))

                if choice in [1, 2]:
                    if st.button("相手のアクションを見る ➡️", use_container_width=True, key=f"btn_go_v1_{street}"):
                        save_to_history()
                        bet_size = data["pot"] * (0.33 if choice == 1 else 0.70)
                        data["pot"] += (bet_size * 2)
                        data["street_history"][street] = "bet"
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_phase = "next_street_trigger"
                        st.rerun()
                else:
                    if st.button("チェック後に相手の対抗ベットを受ける ➡️", use_container_width=True, key=f"btn_go_v_bet_{street}"):
                        save_to_history()
                        data["oop_action_taken"] = "check"
                        st.session_state.quiz_phase = 2
                        st.session_state.quiz_answered = False
                        st.rerun()
                        
        elif st.session_state.quiz_phase == 2:
            villain_bet_size = 0.75 if (barrel_count >= 1 or hand_eq >= 0.85 or range_eq < 0.45) else 0.66
            st.warning(f"🤖 【相手のアクション】ポットの {int(villain_bet_size*100)}% サイズでベットしてきました！")
            
            if street == "flop": best_def = 3 if hand_eq >= 0.75 else (2 if hand_eq >= 0.42 else 1)
            elif street == "turn": best_def = 3 if hand_eq >= 0.78 else (2 if hand_eq >= 0.50 else 1)
            elif street == "river": best_def = 3 if hand_eq >= 0.82 else (2 if hand_eq >= 0.58 else 1)
            
            def_options = ["1: フォールドする", "2: コールする", "3: レイズを返す"]
            ans2 = st.radio("👉 番号を選択してください (1-3):", def_options, key=f"oop_p2_{street}")
            choice2 = int(ans2[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_oop_p2_{street}"):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice2 == best_def)
                    st.session_state.user_choice = choice2
                    st.session_state.best_action = best_def
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success(f"✨ 🎉 【大正解！】最適アクション：{def_options[best_def-1]}")
                else: st.error(f"❌ 【不正解！】あなたの選択：{def_options[choice2-1]} (GTO推奨：{def_options[best_def-1]})")
                
                with st.expander("📊 なぜこの勝率と正解になるの？ディープ数理解説を開く"):
                    st.markdown(generate_deep_mathematical_explanation("oop_p2", choice2, best_def, hand_eq, range_eq, data["pot"], data["pot"] * villain_bet_size))
                
                if st.button("次のステップへ進む ➡️", use_container_width=True, key=f"btn_oop_p2_end_{street}"):
                    save_to_history()
                    if choice2 == 2: data["pot"] += (data["pot"] * villain_bet_size * 2)
                    elif choice2 == 3: data["pot"] += (data["pot"] * villain_bet_size * 4)
                    data["street_history"][street] = "villain_bet"
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()

    else:
        villain_bets = (range_eq < 0.44) and street != "river"
        
        if villain_bets:
            st.warning("🤖 【相手のアクション】ドンクベットを仕掛けてきました！")
            
            if hand_eq >= 0.74: best_ip_def = 3
            elif hand_eq >= 0.42: best_ip_def = 2
            else: best_ip_def = 1
            
            ip_def_opts = ["1: フォールドする", "2: コールする", "3: レイズを返す"]
            ans_ip1 = st.radio("👉 番号を選択してください (1-3):", ip_def_opts, key=f"ip_p1_bet_{street}")
            choice = int(ans_ip1[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_ip_p1_{street}"):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_ip_def)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_ip_def
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success(f"✨ 🎉 【大正解！】最適アクション：{ip_def_opts[best_ip_def-1]}")
                else: st.error(f"❌ 【不正解！】あなたの選択：{ip_def_opts[choice-1]} (GTO推奨：{ip_def_opts[best_ip_def-1]})")
                
                with st.expander("📊 なぜこの勝率と正解になるの？ディープ数理解説を開く"):
                    st.markdown(generate_deep_mathematical_explanation("ip_p1", choice, best_ip_def, hand_eq, range_eq, data["pot"], data["pot"] * 0.66))
                
                if st.button("次のステップへ進む ➡️", use_container_width=True, key=f"btn_ip_p1_end_{street}"):
                    save_to_history()
                    if choice == 2: data["pot"] += (data["pot"] * 0.66 * 2)
                    elif choice == 3: data["pot"] += (data["pot"] * 0.66 * 4)
                    data["street_history"][street] = "bet"
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()
                    
        else:
            st.success("🤖 【相手のアクション】: 💤 チェックしてきました。")
            
            if street == "river":
                best_ip_act = 2 if hand_eq >= 0.66 else (1 if (hand_eq < 0.28 and range_eq >= 0.52) else 3)
            else:
                if hand_eq >= 0.64: best_ip_act = 2
                elif hand_eq >= 0.54: best_ip_act = 1
                elif hand_eq < 0.32 and range_eq >= 0.50: best_ip_act = 1
                else: best_ip_act = 3
                
            ip_check_opts = ["1: 小さくベットを打つ (ポットの33%)", "2: 大きくベットを打つ (ポットの66%〜75%)", "3: チェックバックする"]
            ans_ip2 = st.radio("👉 番号を選択してください (1-3):", ip_check_opts, key=f"ip_p2_check_{street}")
            choice = int(ans_ip2[0])
            
            if not st.session_state.quiz_answered:
                if st.button("決断を確定する 🤝", use_container_width=True, key=f"btn_ip_p2_{street}"):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_ip_act)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_ip_act
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success(f"✨ 🎉 【大正解！】最適アクション：{ip_check_opts[best_ip_act-1]}")
                else: st.error(f"❌ 【不正解！】あなたの選択：{ip_check_opts[choice-1]} (GTO推奨：{ip_check_opts[best_ip_act-1]})")
                
                with st.expander("📊 なぜこの勝率と正解になるの？ディープ数理解説を開く"):
                    st.markdown(generate_deep_mathematical_explanation("ip_p2", choice, best_ip_act, hand_eq, range_eq, data["pot"]))
                
                if st.button("次のステップへ進む ➡️", use_container_width=True, key=f"btn_ip_p2_end_{street}"):
                    save_to_history()
                    action_taken = "check"
                    if choice in [1, 2]:
                        action_taken = "bet"
                        bet_size = data["pot"] * (0.33 if choice == 1 else 0.70)
                        data["pot"] += (bet_size * 2)
                    data["street_history"][street] = action_taken
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()

    if st.session_state.quiz_phase == "next_street_trigger":
        if street == "flop":
            data["current_street"] = "turn"
            st.session_state.quiz_phase = 1
            st.rerun()
        elif street == "turn":
            data["current_street"] = "river"
            st.session_state.quiz_phase = 1
            st.rerun()
        else:
            st.balloons()
            st.subheader(f"🏆 最終ポット総額: {data['pot']:.1f}bb")
            if st.button("次のゲーム（特訓）へ進む 🔄", use_container_width=True, key="btn_next_game"):
                st.session_state.game_state = "setup"
                st.rerun()
