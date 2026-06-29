import streamlit as st
import random
import pandas as pd
import eval7
import copy

# 画面を広くすっきりと使うためにワイドレイアウトに設定し、余計なヘッダーやタイトルを排除
st.set_page_config(page_title="GTO Training", page_icon="🃏", layout="wide")

# --- 1. 定数・レンジ定義 ---
ALL_COLORS = ["薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]

POSITION_OPEN_MIN_COLOR = {
    "UTG": "黄", "LJ":  "緑", "HJ":  "水色", "CO":  "白", "BTN": "グレー＋紫枠", "SB":  "グレー＋紫枠", "BB":  "白"
}

# ポストフロップでのアクション順（左ほど先攻/OOP、右ほど後攻/IP）
POSTFLOP_ORDER = ["SB", "BB", "UTG", "LJ", "HJ", "CO", "BTN"]

@st.cache_data
def load_ranges_from_csv(csv_path="poker_range_list.csv"):
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['hand'], df['color']))
    except:
        return {"AA": "紺", "AKo": "赤", "AQs": "赤", "AKs": "紺", "76s": "白"}

def convert_to_concrete_cards(hand_str):
    ranks = "23456789TJQKA"
    suits = "shcd"
    r1, r2 = hand_str[0], hand_str[1]
    is_suited, is_offsuit = hand_str.endswith('s'), hand_str.endswith('o')
    combos = []
    if r1 == r2:
        for i in range(4):
            for j in range(i + 1, 4): 
                combos.append([r1 + suits[i], r2 + suits[j]])
    elif is_suited:
        for s in suits: 
            combos.append([r1 + s, r2 + s])
    elif is_offsuit or (not is_suited and not is_offsuit):
        for s1 in suits:
            for s2 in suits:
                if s1 != s2: 
                    combos.append([r1 + s1, r2 + s2])
    return combos

def get_range_combos(target_colors, hand_to_color):
    all_combos = []
    for hand, color in hand_to_color.items():
        if color in target_colors: 
            all_combos.extend(convert_to_concrete_cards(hand))
    return all_combos

def is_hero_oop(hero_pos, villain_pos):
    return POSTFLOP_ORDER.index(hero_pos) < POSTFLOP_ORDER.index(villain_pos)

def run_simulation(hero_combos, villain_combos, board, iterations=3000):
    if not hero_combos or not villain_combos: 
        return 0.5
    hero_wins, villain_wins, ties = 0, 0, 0
    actual_iterations = 0
    deck_base = [eval7.Card(f"{r}{s}") for r in "23456789TJQKA" for s in "shcd"]
    
    for _ in range(iterations):
        h_cards_raw = random.choice(hero_combos)
        v_cards_raw = random.choice(villain_combos)
        h_cards = [eval7.Card(c) for c in h_cards_raw]
        v_cards = [eval7.Card(c) for c in v_cards_raw]
        
        used_cards = set(h_cards + v_cards + board)
        if len(used_cards) != len(h_cards) + len(v_cards) + len(board): 
            continue
            
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

def generate_deep_mathematical_explanation(mode, action_idx, best_idx, hand_eq, range_eq, pot):
    h_eq_p = hand_eq * 100
    r_eq_p = range_eq * 100
    board_status = "ドライ" if r_eq_p > 52 else "ウェット"
    
    if r_eq_p >= 53:
        range_adv = "我々のレンジ全体の勝率が高く優位性（レンジアドバンテージ）があります。GTO上、高頻度でベットして圧力をかける局面です。"
    elif r_eq_p <= 47:
        range_adv = "相手（Villain）側にレンジの主導権があります。防衛的にチェックを多用し、レンジ全体の崩壊を防ぐ必要があります。"
    else:
        range_adv = "双方のレンジ勝率が均衡しています。マージナルハンドの扱いに注意し、チェックとベットを緻密にミックスします。"

    if h_eq_p >= 72:
        hand_category = "【純粋なバリューハンド（強ハンド）】"
        hand_logic = "現在のコミット状況において非常に高い勝率を誇ります。ベットやレイズによってバリューを最大化するのが数学的正解（EV最大）です。"
    elif h_eq_p >= 40:
        hand_category = "【マージナルハンド / ショーダウンバリュー】"
        hand_logic = "勝っている可能性は十分ありますが、ベットしてレイズを返されると耐えられないハンドです。GTOではコールやチェックでポットをコントロールします。"
    else:
        hand_category = "【ローエクイティ / フォールドレンジ】"
        hand_logic = "現在の勝率がポットオッズに全く見合っていません。発展性もないため、GTO戦略における最も重要なアクションである『フォールド（Fold）』を選択し、即座にチップの損失を止めるべき局面です。"

    evaluation = "🎉 **あなたの選択はGTO戦略の推奨（EV最大化）と一致しています。**" if action_idx == best_idx else "⚠️ **あなたの選択はGTO戦略から乖離しています。オッズとレンジの連続性を意識しましょう。**"

    return f"""
    **🔍 数学的解析フィードバック ({mode})**
    * あなたの個別ハンド勝率: `{h_eq_p:.1f}%` | レンジ全体の勝率: `{r_eq_p:.1f}%` ({board_status}ボード)
    * レンジ全体の方針: {range_adv}
    * あなたのハンドの分類: {hand_category} — {hand_logic}
    * 判定: {evaluation}
    """

hand_to_color = load_ranges_from_csv()

# セッション状態の初期化
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

if st.session_state.game_state in ["quiz_loop", "villain_folded"]:
    if st.button("↩️ 1手戻る", disabled=(len(st.session_state.history_stack) == 0)):
        pop_history()

# --- 2. セットアップ画面 ---
if st.session_state.game_state == "setup":
    st.session_state.history_stack = []
    pos_choice = st.selectbox(
        "Heroのポジションを選択してください:", 
        ["ランダム", "UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"],
        key="pos_select"
    )
    
    if st.button("ゲームスタート 🚀", use_container_width=True, key="start_btn"):
        all_positions = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
        hero_pos = random.choice(all_positions) if pos_choice == "ランダム" else pos_choice
        
        remaining_positions = [p for p in all_positions if p != hero_pos]
        villain_pos = random.choice(remaining_positions)
        
        if POSTFLOP_ORDER.index(hero_pos) > POSTFLOP_ORDER.index(villain_pos):
            opener, caller = villain_pos, hero_pos
            preflop_summary = f"{villain_pos} のオープンレイズに対し、あなた({hero_pos})がコールして参加しました（あなたがIP）。"
        else:
            opener, caller = hero_pos, villain_pos
            preflop_summary = f"あなた({hero_pos})のオープンレイズに対し、{villain_pos} がコールして参加しました（あなたがOOP）。"
            
        opener_min_color = POSITION_OPEN_MIN_COLOR[opener]
        opener_colors = ALL_COLORS[ALL_COLORS.index(opener_min_color):]
        caller_colors = ALL_COLORS[ALL_COLORS.index("白"):]
        
        hero_colors = opener_colors if hero_pos == opener else caller_colors
        villain_colors = opener_colors if villain_pos == opener else caller_colors
        v_min_color = POSITION_OPEN_MIN_COLOR[villain_pos] if villain_pos == opener else "白(全レンジ)"

        valid_hand_formats = [h for h, c in hand_to_color.items() if c in hero_colors]
        if not valid_hand_formats: valid_hand_formats = ["AA", "KK", "QQ", "AKs"]
        chosen_hand_format = random.choice(valid_hand_formats)
        hero_hand_pair = random.choice(convert_to_concrete_cards(chosen_hand_format))
        hero_hand_raw = f"{hero_hand_pair[0]}{hero_hand_pair[1]}"
        hero_color = hand_to_color.get(chosen_hand_format, "紺")
        
        v_all_possible_combos = get_range_combos(villain_colors, hand_to_color)
        v_valid_combos = [c for c in v_all_possible_combos if c[0] not in hero_hand_pair and c[1] not in hero_hand_pair]
        if not v_valid_combos: v_valid_combos = [["As", "Ah"], ["Ks", "Kh"]]
        villain_hand_pair = random.choice(v_valid_combos)
        villain_hand_raw = f"{villain_hand_pair[0]}{villain_hand_pair[1]}"
            
        deck = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_hand_pair and f"{r}{s}" not in villain_hand_pair]
        random.shuffle(deck)
        
        st.session_state.game_data = {
            "hero_pos": hero_pos,
            "villain_pos": villain_pos,
            "hero_hand_raw": hero_hand_raw,
            "hero_color": hero_color,
            "villain_hand_raw": villain_hand_raw, 
            "villain_colors": villain_colors,
            "v_min_color": v_min_color,
            "preflop_summary": preflop_summary,
            "deck": deck,
            "board": [],
            "pot": 5.5,
            "current_street": "flop",
        }
        st.session_state.game_state = "quiz_loop"
        st.session_state.quiz_phase = 1
        st.session_state.quiz_answered = False
        st.rerun()

# --- 3. 相手フォールド時の専用終了画面（進行バグ修正） ---
elif st.session_state.game_state == "villain_folded":
    data = st.session_state.game_data
    st.markdown(f"### ⚔️ {data['current_street'].upper()} (ゲーム終了)")
    st.success("🤖 相手(Villain)はオッズが合わない（勝率不足）と判断し、正しく【フォールド (Fold)】を選択しました。")
    st.subheader(f"🏆 あなたの勝ちです！ 獲得ポット: {data['pot']:.1f}bb")
    st.info(f"🔍 相手が降ろされた時に実際に持っていた隠しハンド: 【 {data['villain_hand_raw']} 】")
    if st.button("新しいゲームを始める 🔄", use_container_width=True):
        st.session_state.game_state = "setup"
        st.rerun()

# --- 4. クイズ・ゲームコア画面 ---
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
        
    st.markdown(f"### ⚔️ {street.upper()} (現在のポット: {data['pot']:.1f}bb)")
    st.caption(f"状況: {data['preflop_summary']}")
    
    board_html = "".join([f"<span style='font-size: 34px; font-weight: bold; background-color: #262730; padding: 4px 12px; border-radius: 5px; margin-right: 8px; border: 1px solid #464646;'>{c}</span>" for c in data["board"]])
    st.markdown(f"<div style='margin: 15px 0;'>コミュニティボード: &nbsp;&nbsp;{board_html}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**😇 Hero ({data['hero_pos']})**: <span style='font-size: 20px; font-weight: bold; color: #1E90FF;'>{data['hero_hand_raw']}</span> | 位置: `{'OOP(先攻)' if hero_oop else 'IP(後攻)'}`", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**🤖 Villain ({data['villain_pos']})**: <span style='font-size: 20px; font-weight: bold; color: #FF4500;'>[??]</span> | レンジ基準: `【{data['v_min_color']}】以上`", unsafe_allow_html=True)
        
    hero_single_combo = [[data['hero_hand_raw'][0:2], data['hero_hand_raw'][2:4]]]
    villain_single_combo = [[data['villain_hand_raw'][0:2], data['villain_hand_raw'][2:4]]]
    
    hero_range_combos = get_range_combos([data['hero_color']], hand_to_color)
    villain_range_combos = get_range_combos(data['villain_colors'], hand_to_color)
    board_obj = [eval7.Card(c) for c in data["board"]]
    
    hand_eq = run_simulation(hero_single_combo, villain_range_combos, board_obj, iterations=3000)
    range_eq = run_simulation(hero_range_combos, villain_range_combos, board_obj, iterations=3000)
    villain_hand_eq = run_simulation(villain_single_combo, hero_range_combos, board_obj, iterations=3000)
    
    st.caption(f"現在の状況の推定： あなたのハンド勝率: {hand_eq*100:.1f}% | あなたのレンジ勝率: {range_eq*100:.1f}%")
    st.markdown("---")
    
    # --- 【OOP (先攻) 時のロジック】 ---
    if hero_oop:
        if st.session_state.quiz_phase == 1:
            st.write("👉 先攻です。最初のアクションを選択してください:")
            best_act = 3 if hand_eq < 0.55 else (2 if hand_eq >= 0.72 else 1)
            
            options = ["1: ベット (ポットの33%)", "2: ベット (ポットの70%)", "3: チェック (Check)"]
            ans = st.radio("選択:", options, key=f"oop_p1_{street}", label_visibility="collapsed")
            choice = int(ans[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_act)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_act
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success("🎉 正解です！GTO的に最適なラインです。")
                else: st.error(f"❌ 不正解です (GTO推奨アクション: {options[best_act-1]})")
                st.info(generate_deep_mathematical_explanation("OOP・第1アクション", choice, best_act, hand_eq, range_eq, data["pot"]))

                if choice in [1, 2]:
                    if st.button("相手(Villain)の対抗判断を受ける ➡️"):
                        save_to_history()
                        bet_size = data["pot"] * (0.33 if choice == 1 else 0.70)
                        
                        # 相手のコールに必要な勝率をオッズ計算
                        odds_required = 0.33 / (1 + 2 * 0.33) if choice == 1 else 0.70 / (1 + 2 * 0.70)
                        if villain_hand_eq >= odds_required:
                            data["pot"] += (bet_size * 2)
                            st.session_state.quiz_answered = False
                            st.session_state.quiz_phase = "next_street_trigger"
                        else:
                            st.session_state.game_state = "villain_folded"
                            st.session_state.quiz_answered = False
                        st.rerun()
                else:
                    if st.button("相手(Villain)のアクションへ進む ➡️"):
                        save_to_history()
                        st.session_state.quiz_phase = 2
                        st.session_state.quiz_answered = False
                        st.rerun()
                        
        elif st.session_state.quiz_phase == 2:
            v_bet_pct = 0.70 if villain_hand_eq >= 0.65 else (0.33 if villain_hand_eq < 0.25 and range_eq < 0.47 else 0.0)
            
            if v_bet_pct == 0.0:
                st.success("🤖 相手はチェックバックしました。")
                if st.button("次へ進む ➡️"):
                    save_to_history()
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()
            else:
                st.warning(f"🤖 相手がポットの {int(v_bet_pct*100)}% サイズでベットしてきました！")
                
                pot_odds = v_bet_pct / (1 + 2 * v_bet_pct)
                if hand_eq < pot_odds: best_def = 1  # Fold
                elif hand_eq >= 0.74: best_def = 3   # Raise
                else: best_def = 2                   # Call
                    
                def_options = ["1: フォールド (Fold)", "2: コール (Call)", "3: レイズ (Raise)"]
                ans2 = st.radio("ディフェンスの選択:", def_options, key=f"oop_p2_{street}", label_visibility="collapsed")
                choice2 = int(ans2[0])
                
                if not st.session_state.quiz_answered:
                    if st.button("アクションを確定する", use_container_width=True):
                        save_to_history()
                        st.session_state.quiz_answered = True
                        st.session_state.is_correct = (choice2 == best_def)
                        st.session_state.user_choice = choice2
                        st.session_state.best_action = best_def
                        st.rerun()
                else:
                    if st.session_state.is_correct: st.success("🎉 正解です！")
                    else: st.error(f"❌ 不正解です (GTO推奨アクション: {def_options[best_def-1]})")
                    st.info(generate_deep_mathematical_explanation("OOP・防衛フェーズ", choice2, best_def, hand_eq, range_eq, data["pot"]))
                    
                    if choice2 == 1:
                        st.error("フォールドしたためゲーム終了です。チップを失うリスクを回避しました。")
                        if st.button("新しいゲームを始める 🔄", use_container_width=True):
                            st.session_state.game_state = "setup"
                            st.rerun()
                    else:
                        if st.button("次へ進む ➡️"):
                            save_to_history()
                            if choice2 == 2: 
                                data["pot"] += (data["pot"] * v_bet_pct * 2)
                            st.session_state.quiz_answered = False
                            st.session_state.quiz_phase = "next_street_trigger"
                            st.rerun()

    # --- 【IP (後攻) 時のロジック】 ---
    else:
        # 相手がドンクベット（先攻からベット）してくる基準
        villain_donk = (villain_hand_eq >= 0.70 and range_eq < 0.45 and street != "river")
        
        if villain_donk:
            st.warning("🤖 相手(Villain)が先攻からドンクベット(ポットの66%)を仕掛けてきました！")
            
            # 【動的オッズ計算修正】66%ベットに対するオッズ計算
            donk_odds = 0.66 / (1 + 2 * 0.66) # 28.4%
            if hand_eq < donk_odds: best_ip_def = 1   # Fold
            elif hand_eq >= 0.72: best_ip_def = 3     # Raise
            else: best_ip_def = 2                     # Call
            
            ip_def_opts = ["1: フォールド (Fold)", "2: コール (Call)", "3: レイズ (Raise)"]
            ans_ip1 = st.radio("対応選択:", ip_def_opts, key=f"ip_p1_bet_{street}", label_visibility="collapsed")
            choice = int(ans_ip1[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_ip_def)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_ip_def
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success("🎉 正解です！")
                else: st.error(f"❌ 不正解です (GTO推奨: {ip_def_opts[best_ip_def-1]})")
                
                if choice == 1:
                    st.error("フォールドを選択したためゲーム終了です。")
                    if st.button("新しいゲームを始める 🔄", use_container_width=True):
                        st.session_state.game_state = "setup"
                        st.rerun()
                else:
                    if st.button("次へ進む ➡️"):
                        save_to_history()
                        if choice == 2: 
                            data["pot"] += (data["pot"] * 0.66 * 2)
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_phase = "next_street_trigger"
                        st.rerun()
        else:
            st.success("🤖 相手(Villain)はチェックを選択しました。あなたのアクション番です。")
            best_ip_act = 3 if hand_eq < 0.54 else (2 if hand_eq >= 0.68 else 1)
            
            ip_check_opts = ["1: ベット (ポットの33%)", "2: ベット (ポットの70%)", "3: チェックバック (ポッドコントロール)"]
            ans_ip2 = st.radio("アクション選択:", ip_check_opts, key=f"ip_p2_check_{street}", label_visibility="collapsed")
            choice = int(ans_ip2[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_ip_act)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_ip_act
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success("🎉 正解です！")
                else: st.error(f"❌ 不正解です (GTO推奨: {ip_check_opts[best_ip_act-1]})")
                
                if st.button("相手の対抗結果を確認して次へ進む ➡️"):
                    save_to_history()
                    if choice in [1, 2]:
                        bet_size = data["pot"] * (0.33 if choice == 1 else 0.70)
                        odds_required = 0.33 / (1 + 2 * 0.33) if choice == 1 else 0.70 / (1 + 2 * 0.70)
                        
                        if villain_hand_eq >= odds_required:
                            data["pot"] += (bet_size * 2)
                            st.session_state.quiz_answered = False
                            st.session_state.quiz_phase = "next_street_trigger"
                        else:
                            st.session_state.game_state = "villain_folded"
                            st.session_state.quiz_answered = False
                    else:
                        # チェックバック時はそのストリートが終了
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()

    # --- ストリートを次に進めるトリガー処理 ---
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
            # リバー完了時の最終処理（ショーダウン移行）
            st.balloons()
            st.markdown("### 🏆 ショーダウン（リバー完了）")
            st.subheader(f"最終獲得ポット: {data['pot']:.1f}bb")
            st.info(f"🔍 **相手（Villain）が実際に最後まで隠し持っていたハンド: 【 {data['villain_hand_raw']} 】**")
            
            h_score = eval7.evaluate([eval7.Card(c) for c in [data['hero_hand_raw'][0:2], data['hero_hand_raw'][2:4]]] + board_obj)
            v_score = eval7.evaluate([eval7.Card(c) for c in [data['villain_hand_raw'][0:2], data['villain_hand_raw'][2:4]]] + board_obj)
            if h_score > v_score:
                st.success("✨ ショーダウンの結果、あなたのハンドが勝っていました！")
            elif v_score > h_score:
                st.error("惨敗…！相手のハンドの方が強かったです。")
            else:
                st.warning("残ったポットを分け合います（引き分け）。")
                
            if st.button("もう一度新しいシチュエーションで練習する 🔄", use_container_width=True):
                st.session_state.game_state = "setup"
                st.rerun()
