import streamlit as st
import random
import pandas as pd
import eval7
import copy

st.set_page_config(page_title="GTO特訓ツール（究極進化版）", page_icon="🃏", layout="centered")

POSITION_RULES = {
    "UTG": {"open": ["紺", "赤", "黄"]},
    "HJ":  {"open": ["紺", "赤", "黄", "緑"]},
    "CO":  {"open": ["紺", "赤", "黄", "緑", "水色"]},
    "BTN": {"open": ["紺", "赤", "黄", "緑", "水色", "白", "グレー＋紫枠"]},
    "SB":  {"open": ["紺", "赤", "黄", "緑", "水色", "白"]},
    "BB":  {"open": ["紺", "赤", "黄", "緑", "水色", "白"]}
}

ALL_COLORS = ["薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]
POSITIONS_LIST = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]

@st.cache_data
def load_ranges_from_csv(csv_path="poker_range_list.csv"):
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['hand'], df['color']))
    except:
        return {"AA": "紺", "AKo": "赤", "AQs": "赤", "AhJh": "黄", "KhQh": "緑", "76s": "水色"}

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

def determine_dynamic_ranges(hero_pos, villain_pos):
    hero_open_colors = POSITION_RULES[hero_pos]["open"]
    if villain_pos == "BB":
        return ALL_COLORS[max(0, ALL_COLORS.index(hero_open_colors[-1]) - 1):]
    if villain_pos == "SB":
        return ALL_COLORS[ALL_COLORS.index(hero_open_colors[-1]):]
    return ALL_COLORS[min(len(ALL_COLORS) - 1, ALL_COLORS.index(hero_open_colors[-1]) + 1):]

def run_simulation(hero_combos, villain_combos, board, iterations=10000):
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

def is_hero_oop(hero_pos, villain_pos):
    order = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
    return order.index(hero_pos) < order.index(villain_pos)

# --- 💡 ディープ数理・勝率根拠・オッズロジック解説ジェネレーター ---
def generate_deep_mathematical_explanation(mode, action_idx, best_idx, hand_eq, range_eq, pot, bet_size=0.0):
    eq_p = hand_eq * 100
    req_p = range_eq * 100
    
    # 共通のMDFやオッズ計算の数式テキスト
    odds_text = ""
    if bet_size > 0:
        required_eq = (bet_size / (pot + bet_size * 2)) * 100
        odds_text = f"\n\n**【数理オッズ計算】**\n相手のベットに対し、コールに必要なエキティ（必要勝率）は $$\\text{{必要勝率}} = \\frac{{\\text{{コール額}}}}{{\\text{{現在のポット}} + \\text{{コール額}} + \\text{{相手のベット額}}}} = {required_eq:.1f}\\%$$ です。あなたのハンド勝率は **{eq_p:.1f}%** であるため、この必要ラインを"
        if eq_p >= required_eq:
            odds_text += f" **上回っており(+$E[V]$)、数学的にコールが正当化** されます。"
        else:
            odds_text += f" **下回っており(-$E[V]$)、長期的にフォールドが絶対正義** となります。"

    base_html = f"""
    #### 📊 GTO数理・勝率のディープ解析
    1. **なぜこの勝率（{eq_p:.1f}%）になるのか？**
       * 相手（Villain）のプリフロップ防衛レンジ全体に対し、現在のボード状況であなたの手札が「どれだけ勝っているか」を10,000回シミュレーションした結果です。
       * レンジ全体の勝率が **{req_p:.1f}%** であるため、{'あなたの方が全体的に強いレンジを持っています（レンジアドバンテージ有り）。' if req_p >= 50 else '相手の方がレンジの密度が濃く、あなたはレンジ上やや不利な状況です。'}
    2. **なぜ推奨アクション（選択肢 {best_idx}）が最善なのか？**
       * ポーカーのGTO（ゲーム理論最適化）は、自分のハンドの強さ（SDV）だけでなく、**「このサイズでベットして、自分より弱い手がコールしてくれるか？」「チェックして相手にブラフをインデュースできるか？」**の期待値（EV）の合計が最大になるように計算されます。
    """
    return base_html + odds_text

def get_detailed_explanation(mode, action_idx, hand_eq, range_eq):
    eq_p = hand_eq * 100
    req_p = range_eq * 100
    if mode == "oop_p1":
        if action_idx == 1:
            return f"【33%ベットを選択した場合】\n現在のハンド勝率 {eq_p:.1f}% / レンジ勝率 {req_p:.1f}%。マージナルな強さで薄くバリューを取りたい時、またはハンド単体は弱くともレンジアドバンテージ（目安53%以上）を盾にプロテクション目的のC-BETとして33%の小サイズはGTO上極めて有効な防衛攻撃となります。"
        elif action_idx == 2:
            return f"【66%〜75%ベットを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。勝率が圧倒的に高く（目安68%以上）、ボードにドローが多い場合、相手のコールレンジから最大の期待値（EV）を毟り取るために大きなサイズが正当化されます。逆に中途半端な手や超モンスターハンド（トラップを仕掛けるべき局面）での大ベットは、相手の弱い手をすべて降ろしてしまい、自分のEVを大きく損なう原因になります。"
        elif action_idx == 3:
            return f"【チェックを選択した場合】\n現在のハンド勝率 {eq_p:.1f}% / レンジ勝率 {req_p:.1f}%。先攻（OOP）は常にポジションの不利を背負っているため、ハンドやレンジの勝率が十分でない場合は『チェック』を高頻度で混ぜて防衛ラインを敷くのがナッシュ均衡の基本です。また、勝率が85%を超える無敵状態であれば、あえてチェックすることで相手に『ブラフや薄いベットを打たせる（インデュース）』という至高のトラップ戦略に昇華されます。"
    elif mode == "oop_p2":
        if action_idx == 1:
            return f"【フォールドを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。相手は連続してストリートを打ってきている（バレル）、またはボードテクスチャに対して強いレンジを持っています。自分のハンド勝率がポットオッズ（必要勝率）を下回っている場合、未練を残さず即座にフォールドするのが長期的な損失をゼロにする最善のGTOディフェンスです。"
        elif action_idx == 2:
            return f"【コールを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。自分の手は相手のガチガチのバリュー（超強手）には負けているかもしれませんが、相手のブラフレンジ（ブラフバレル）を捕まえるには十分な勝率を持っています。オッズに合うためコールして次のカード、あるいはショーダウンを目指す『ブラフキャッチャー』としての役割を果たします。"
        elif action_idx == 3:
            return f"【レイズを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。勝率が極めて高く（目安75%以上）、ナッツ級の手を隠し持っている（チェックトラップ成功時）場合、相手が自ら大きく打ってくれたこの瞬間こそが、相手のスタックを全額没収する最大のチャンスです。ここでコールに留めると大損失（バリューロス）になります。強烈なチェックレイズでポットを爆発させましょう。"
    elif mode == "ip_p1":
        if action_idx == 1:
            return f"【フォールドを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。後攻（IP）の優位性があるとはいえ、相手のドンクベットや先攻100%バレルに対し、自分のハンドが完全にオッズ負けしています。無駄なチップを流さないための正しい撤退です。"
        elif action_idx == 2:
            return f"【コールを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。後攻の利（ポジション優位）を最大限に活かし、コールに留めることで次のストリートでも相手の出方（チェックか、さらなるベットか）をコントロールできます。中位の強さの手で広くコールを留めるのはGTOの定石です。"
        elif action_idx == 3:
            return f"【レイズを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。勝率75%以上のモンスターハンドであれば、後攻から即座に主導権を奪い返し、コミットメント（降りられない状態）に相手を追い込むためのレイズを返すのがバリュー最大化の正解となります。"
    elif mode == "ip_p2":
        if action_idx == 1:
            return f"【33%ベットを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。相手のチェックにより弱みが露呈したのに対し、レンジ全体の優位性（目安50%以上）を使って薄くバリューを剥ぎ取る、あるいは相手のハイカード（AK等）をフォールドさせるピュアブラフとして機能します。"
        elif action_idx == 2:
            return f"【66%〜75%ベットを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。明確なバリューハンド（目安勝率64%以上）を保持しているため、チェックした相手のミドルペアやドローハンドに対して高額の通行料を要求し、ポットを効率的に大きくします。"
        elif action_idx == 3:
            return f"【チェックバックを選択した場合】\n現在のハンド勝率 {eq_p:.1f}%。特にリバーにおいては、中途半端な強さの手でベットしてレイズを返されるのが最悪のシナリオです。チェックバックで安全に無料のショーダウン（SDVの利確）を行い、勝利を確定させるのが鉄則です。"
    return ""

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
    """現在の状態のディープコピーを履歴スタックに保存（1手戻る用）"""
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
    """直前の履歴を取り出して復元する"""
    if st.session_state.history_stack:
        prev = st.session_state.history_stack.pop()
        st.session_state.game_data = prev["game_data"]
        st.session_state.quiz_phase = prev["quiz_phase"]
        st.session_state.quiz_answered = prev["quiz_answered"]
        st.session_state.is_correct = prev["is_correct"]
        st.session_state.user_choice = prev["user_choice"]
        st.session_state.best_action = prev["best_action"]
        st.rerun()

st.title("🃏 GTO究極")

# 常時上部に「1手戻る」ボタンを表示（戻れる履歴がある場合のみ活性化）
if st.session_state.game_state == "quiz_loop":
    col_back, col_space = st.columns([1, 4])
    with col_back:
        if st.button("↩️ 1手戻る", disabled=(len(st.session_state.history_stack) == 0), use_container_width=True):
            pop_history()

# --- 1. セットアップ画面 ---
if st.session_state.game_state == "setup":
    st.session_state.history_stack = [] # 初期化
    st.subheader("🛠️ トレーニング設定")
    pos_choice = st.selectbox(
        "練習したい自分のポジション(Hero)を選択してください:", 
        ["ランダム", "UTG", "HJ", "CO", "BTN (後攻の練習に最適)", "SB (先攻の練習に最適)", "BB"],
        key="pos_select"
    )
    
    if st.button("ゲームに挑む 🚀", use_container_width=True, key="start_btn"):
        clean_choice = pos_choice.split(" ")[0]
        if clean_choice == "ランダム":
            hero_pos = random.choice(POSITIONS_LIST)
        else:
            hero_pos = clean_choice
            
        villain_pos = random.choice([p for p in POSITIONS_LIST if p != hero_pos])
        
        allowed_colors = POSITION_RULES[hero_pos]["open"]
        chosen_hand_format = random.choice([h for h, c in hand_to_color.items() if c in allowed_colors])
        hero_hand_pair = random.choice(convert_to_concrete_cards(chosen_hand_format))
        hero_hand_raw = f"{hero_hand_pair[0]}{hero_hand_pair[1]}"
        hero_color = hand_to_color[chosen_hand_format]
        villain_colors = determine_dynamic_ranges(hero_pos, villain_pos)
        
        deck = [f"{r}{s}" for r in "23456789TJQKA" for s in "shcd" if f"{r}{s}" not in hero_hand_pair]
        random.shuffle(deck)
        
        st.session_state.game_data = {
            "hero_pos": hero_pos,
            "villain_pos": villain_pos,
            "hero_hand_raw": hero_hand_raw,
            "hero_color": hero_color,
            "villain_colors": villain_colors,
            "deck": deck,
            "board": [],
            "pot": 5.5,
            "street_history": {},
            "current_street": "flop",
            "oop_action_taken": None
        }
        st.session_state.game_state = "quiz_loop"
        st.session_state.quiz_phase = 1
        st.session_state.quiz_answered = False
        st.rerun()

# --- 2. ガチクイズコア画面 ---
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
        
    st.markdown(f"### ⚔️ 【クイズ】{street.upper()} (現在のポット: {data['pot']:.1f}bb)")
    
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**あなた (Hero)**: `{data['hero_pos']}` (【{data['hero_color']}】レンジ)")
            st.markdown(f"**手札**: `{data['hero_hand_raw']}` | ポジション: `{'先攻(OOP)' if hero_oop else '後攻(IP)'}`")
        with col2:
            st.markdown(f"**相手 (Villain)**: `{data['villain_pos']}`")
            st.markdown(f"**敵レンジ**: {', '.join(data['villain_colors'])}")
            
    st.info(f"📁 **現在のボード**: `{' '.join(data['board'])}`  |  💰 **ポット**: {data['pot']:.1f}bb")
    
    hero_single_combo = [[data['hero_hand_raw'][0:2], data['hero_hand_raw'][2:4]]]
    hero_range_combos = get_range_combos([data['hero_color']], hand_to_color)
    villain_range_combos = get_range_combos(data['villain_colors'], hand_to_color)
    board_obj = [eval7.Card(c) for c in data['board']]
    
    with st.spinner("🧠 10,000回GTOシミュレーション演算中..."):
        hand_eq = run_simulation(hero_single_combo, villain_range_combos, board_obj, iterations=10000)
        range_eq = run_simulation(hero_range_combos, villain_range_combos, board_obj, iterations=10000)
        
    c_eq1, c_eq2 = st.columns(2)
    c_eq1.metric(label="📊 あなたのハンド勝率", value=f"{hand_eq*100:.1f} %")
    c_eq2.metric(label="📈 レンジ全体の勝率", value=f"{range_eq*100:.1f} %")
    st.markdown("---")
    
    hero_bet_count = list(data["street_history"].values()).count("bet")
    barrel_count = list(data["street_history"].values()).count("villain_bet")
    
    # --- パターンA: 【先攻(OOP)】の処理群 ---
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
                    save_to_history() # 巻き戻しポイント保存
                    st.session_state.quiz_answered = True
                    st.session_state.is_correct = (choice == best_act)
                    st.session_state.user_choice = choice
                    st.session_state.best_action = best_act
                    st.rerun()
            else:
                if st.session_state.is_correct: st.success(f"✨ 【正解です！】最適アクション：{options[best_act-1]}")
                else: st.error(f"❌ 【不正解！】あなたの選択：{options[choice-1]} (GTO推奨：{options[best_act-1]})")
                
                st.info(get_detailed_explanation("oop_p1", choice, hand_eq, range_eq))
                
                # 🛠️ オンデマンド深掘り数理解説アコーディオン
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
            st.warning(f"🤖 【相手({data['villain_pos']})のアクション】ポットの {int(villain_bet_size*100)}% サイズで【最適化ベット】してきました！")
            st.markdown("### 【相手のベットに対するあなたの決断は？】")
            
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
                
                st.info(get_detailed_explanation("oop_p2", choice2, hand_eq, range_eq))
                
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

# --- パターンB: 【後攻(IP)】の処理群 ---
    else:
        villain_bets = (range_eq < 0.46) and street != "river"
        
        if villain_bets:
            st.warning(f"🤖 【相手({data['villain_pos']})のアクション】レンジ有利を活かしポットの66%サイズで【最適化ベット】してきました！")
            st.markdown("### 【ベットされたあなた(IP)のアクションは？】")
            
            if hand_eq >= 0.75: best_ip_def = 3
            elif hand_eq >= 0.44: best_ip_def = 2
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
                
                st.info(get_detailed_explanation("ip_p1", choice, hand_eq, range_eq))
                
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
            st.success(f"🤖 【相手({data['villain_pos']})のアクション】: 💤 レンジ均衡を保つため【チェック】してきました。")
            st.markdown("### 【チェックで回ってきたあなた(IP)のアクションは？】")
            
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
                
                st.info(get_detailed_explanation("ip_p2", choice, hand_eq, range_eq))
                
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

    # --- 各ストリート終了後の進級トリガー ---
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
            st.subheader(f"🏆 リバーまで終了しました！ 最終ポット総額: {data['pot']:.1f}bb")
            if st.button("次のゲーム（特訓）へ進む 🔄", use_container_width=True, key="btn_next_game"):
                st.session_state.game_state = "setup"
                st.rerun()
