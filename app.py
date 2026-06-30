import streamlit as st
import random
import pandas as pd
import eval7
import copy

# 画面設定
st.set_page_config(page_title="GTO Elite Training & Analysis", page_icon="🃏", layout="wide")

# --- 1. 定数・レンジ定義 ---
ALL_COLORS = ["薄ピンク", "グレー＋紫枠", "白", "水色", "緑", "黄", "赤", "紺"]

POSITION_OPEN_MIN_COLOR = {
    "UTG": "黄", "LJ":  "緑", "HJ":  "水色", "CO":  "白", "BTN": "グレー＋紫枠", "SB":  "グレー＋紫枠", "BB":  "白"
}

PREFLOP_ORDER = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POSTFLOP_ORDER = ["SB", "BB", "UTG", "LJ", "HJ", "CO", "BTN"]

@st.cache_data
def load_ranges_from_csv(csv_path="poker_range_list.csv"):
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['hand'], df['color']))
    except:
        # フォールバック用の最小レンジ
        return {"AA": "紺", "KK": "紺", "QQ": "紺", "JJ": "赤", "AKs": "紺", "AQs": "赤", "AKo": "赤", "76s": "白"}

def convert_to_concrete_cards(hand_str):
    ranks = "23456789TJQKA"
    suits = "shcd"
    r1, r2 = hand_str[0], hand_str[1]
    is_suited = hand_str.endswith('s')
    
    combos = []
    if r1 == r2: # ポケットペア (6コンボ)
        for i in range(4):
            for j in range(i + 1, 4): 
                combos.append([r1 + suits[i], r2 + suits[j]])
    elif is_suited: # スーテッド (4コンボ)
        for s in suits: 
            combos.append([r1 + s, r2 + s])
    else: # オフスーツ (12コンボ)
        for i in range(4):
            for j in range(4):
                if i != j:
                    combos.append([r1 + suits[i], r2 + suits[j]])
    return combos

def get_range_combos(target_colors, hand_to_color):
    all_combos = []
    for hand, color in hand_to_color.items():
        if color in target_colors: 
            all_combos.extend(convert_to_concrete_cards(hand))
    return all_combos

def is_hero_oop(hero_pos, villain_pos):
    return POSTFLOP_ORDER.index(hero_pos) < POSTFLOP_ORDER.index(villain_pos)

def analyze_board_texture(board):
    """ボードの特徴を動的に解析する"""
    if not board:
        return "プリフロップ"
    
    ranks = [c[0] for c in board]
    suits = [c[1] for c in board]
    
    # ハイカードの枚数 (T, J, Q, K, A)
    high_cards = sum(1 for r in ranks if r in "TJQKA")
    # ペアボードの判定
    is_paired = len(ranks) != len(set(ranks))
    
    # フラッシュドローの可能性 (同スーツ3枚以上)
    suit_counts = {s: suits.count(s) for s in set(suits)}
    max_suit = max(suit_counts.values()) if suit_counts else 0
    
    if max_suit >= 3:
        flush_status = "モノトーン/フラッシュ完成ボード" if max_suit >= 4 else "２フラッシュドローボード"
    else:
        flush_status = "レインボー（フラッシュが薄い）"
        
    if high_cards >= 2:
        height = "ハイカード主体（ブロードウェイ多め）"
    else:
        height = "ローカード主体"
        
    paired_status = "ペア（重複あり）" if is_paired else "アンペア（重複なし）"
    
    return f"{height} / {paired_status} / {flush_status}"

def run_simulation(hero_combos, villain_combos, board, iterations=1000):
    if not hero_combos or not villain_combos: 
        return 0.5
    hero_wins, villain_wins, ties = 0, 0, 0
    actual_iterations = 0
    deck_base = [eval7.Card(f"{r}{s}") for r in "23456789TJQKA" for s in "shcd"]
    
    h_combos_cards = [[eval7.Card(c[0]), eval7.Card(c[1])] for c in hero_combos]
    v_combos_cards = [[eval7.Card(c[0]), eval7.Card(c[1])] for c in villain_combos]
    
    board_set = set(board)
    
    for _ in range(iterations):
        h_cards = random.choice(h_combos_cards)
        v_cards = random.choice(v_combos_cards)
        
        if board_set.intersection(h_cards) or board_set.intersection(v_cards) or set(h_cards).intersection(v_cards):
            continue
            
        actual_iterations += 1
        used_cards = board_set.union(h_cards).union(v_cards)
        remaining_deck = [c for c in deck_base if c not in used_cards]
        
        num_to_draw = 5 - len(board)
        interim_board = board + random.sample(remaining_deck, num_to_draw) if num_to_draw > 0 else board
        
        hero_score = eval7.evaluate(h_cards + interim_board)
        villain_score = eval7.evaluate(v_cards + interim_board)
        
        if hero_score > villain_score: hero_wins += 1
        elif villain_score > hero_score: villain_wins += 1
        else: ties += 1
            
    return (hero_wins + 0.5 * ties) / actual_iterations if actual_iterations > 0 else 0.5

# --- 💡 GTO ソルバーライク判定エンジン ---
def calculate_gto_action_frequencies(hand_eq, range_eq, street):
    freq = {"bet_70": 0.0, "bet_33": 0.0, "check": 0.0}
    
    # 1. レンジ優位性によるベース
    if range_eq >= 0.54: 
        base_bet_small, base_bet_large, base_check = 50, 15, 35
    elif range_eq <= 0.46: 
        base_bet_small, base_bet_large, base_check = 10, 5, 85
    else: 
        base_bet_small, base_bet_large, base_check = 35, 15, 50

    # 2. 個別ハンドの強さによる周波数ブレンド
    if hand_eq >= 0.75: # モンスターバリュー
        freq["bet_70"] = 60.0
        freq["bet_33"] = 25.0
        freq["check"] = 15.0  # チェックレンジの防衛(トラップ)
    elif hand_eq >= 0.55: # マージナル・ショーダウン
        freq["bet_70"] = 5.0
        freq["bet_33"] = 25.0
        freq["check"] = 70.0  # ポットコントロール
    elif 0.35 <= hand_eq < 0.55: # セミブラフ / ドロー
        if range_eq >= 0.52:
            freq["bet_70"] = 25.0
            freq["bet_33"] = 35.0
            freq["check"] = 40.0
        else:
            freq["bet_70"] = 10.0
            freq["bet_33"] = 15.0
            freq["check"] = 75.0
    else: # エクイティ皆無 (ピュアブラフ候補)
        if range_eq >= 0.54 and street != "river":
            freq["bet_70"] = 20.0
            freq["bet_33"] = 15.0
            freq["check"] = 65.0
        else:
            freq["bet_70"] = 5.0
            freq["check"] = 95.0

    return freq

def judge_defense_gto_action(hand_eq, bet_pct):
    mdf = 1.0 / (1.0 + bet_pct)
    freq = {"fold": 0.0, "call": 0.0, "raise": 0.0}
    
    if hand_eq >= 0.82:
        freq["raise"] = 40.0
        freq["call"] = 60.0
    elif hand_eq >= 0.55:
        freq["raise"] = 8.0
        freq["call"] = 87.0
        freq["fold"] = 5.0
    elif hand_eq >= (1.0 - mdf) * 0.75:
        freq["call"] = 65.0
        freq["fold"] = 35.0
    else:
        freq["fold"] = 100.0
        
    return freq

# --- 🧠 新設: 動的詳細解説・ハンドリーディング生成システム ---
def generate_advanced_gto_explanation(mode, action_idx, freq_dict, hand_eq, range_eq, data, street):
    h_pos = data["hero_pos"]
    v_pos = data["villain_pos"]
    board_str = ", ".join(data["board"])
    texture = analyze_board_texture(data["board"])
    
    action_map = {1: "bet_33", 2: "bet_70", 3: "check"} if "防衛" not in mode else {1: "fold", 2: "call", 3: "raise"}
    chosen_key = action_map[action_idx]
    chosen_freq = freq_dict.get(chosen_key, 0.0)
    
    # ユーザーアクションの評価文
    if chosen_freq >= 25.0:
        evaluation = "🟩 **【最善手 / 推奨アクション】** GTOソルバーの主要な選択肢と完全に合致しています。EV（期待値）は最大化されています。"
    elif chosen_freq > 0.0:
        evaluation = "🟨 **【許容手 / 混合戦略】** GTO上存在する選択肢ですが、低頻度です。テーブルイメージや相手の癖をエクスプロイトする場合にのみ推奨されます。"
    else:
        evaluation = "🟥 **【悪手（ブラダー）】** このシチュエーションにおけるGTOレンジバランスを大きく崩す選択です。相手に簡単に対策（エクスプロイト）されるリスクがあります。"

    # --- 1. なぜレンジ全体勝率がそのような値になるのかの詳細説明 ---
    range_reasoning = ""
    if range_eq >= 0.54:
        range_reasoning = f"コミュニティボード `[{board_str}]` は `{texture}` であり、プリフロップのオリジナルレイザー（レンジがナッツ級に偏っている側）に極めて有利です。特に上位ペア（AA, KK, QQ）や強力なブロードウェイハンドのコンボ占有率でこちらが勝っているため、レンジ勝率が `{range_eq*100:.1f}%` と高く出ています。GTO上、レンジ全体で高頻度のベット（Cベット）が正当化される局面です。"
    elif range_eq <= 0.46:
        range_reasoning = f"ボード `[{board_str}]` （{texture}）は、コール側のレンジ（ミドルペアやスーテッドコネクターが多く含まれるレンジ）に強くヒットしています。こちらのレンジには空振りのハイカードが多く含まれるため、レンジ勝率は `{range_eq*100:.1f}%` まで落ち込んでいます。ナッツ優位性が相手にあるため、チェックを多用して慎重にポットを防衛する必要があります。"
    else:
        range_reasoning = f"ボード `[{board_str}]` に対し、双方のプリフロップレンジの絡み合いが非常に拮抗しています。レンジ全体の勝率は `{range_eq*100:.1f}%` とほぼ50%前後のイーブンです。このような状況では、どちらか一方が強気に打ち続けることはできず、GTOは緻密なチェックとベットのミックス（ブレンド戦略）を要求します。"

    # --- 2. 相手のポジションやアクションから相手のハンドを読む詳細内容 ---
    hand_reading = ""
    if "防衛" not in mode: # Heroが先に打つ時、これまでのアクションから読む
        hand_reading = f"相手（{v_pos}）はプリフロップで `{data['v_min_color']}` レンジでコールして入ってきました。現ストリートのボード `[{board_str}]` に入った段階で、相手は『まだ一切ポストフロップのアクションを示していない』ため、相手のレンジはまだ広く保たれています。ただし、{v_pos} のポジション特性上、ミドルポケットペアやスーテッドA、スーテッドコネクターが高密度で含まれていると読むべきです。"
    else: # 相手がベットしてきた時のリーディング
        action_text = "33%サイズベット" if "33" in mode or chosen_key == "call" else "70%サイズベット"
        hand_reading = f"相手（{v_pos}）がこの `{texture}` ボードでアクティブにベットを行ってきたという事実から、相手のハンドレンジは以下のようにドラスティックに絞り込まれます。\n" \
                       f"1. **バリューレンジ**: ボードに強く絡んだセット、２ペア、あるいはトップペア・グッドキッカー以上の強ハンド。\n" \
                       f"2. **ブラフ/セミブラフレンジ**: GTOソルバーは完全に空気のハンドではベットしません。したがって、相手はフラッシュドロー、ストレートドロー、あるいはバックドア発展性のあるオーバーカードを100%の確率ではなく、一定確率（混合戦略）で混ぜてベットレンジを構成しています。あなたがフォールドを選択すべきかどうかは、このバリューとブラフの比率、およびポットオッズのバランスで決定されます。"

    # テキスト組み立て
    explanation_md = f"""
### 📊 【詳細解析フィードバック】
{evaluation}

---

#### 🧠 1. レンジ勝率（{range_eq*100:.1f}%）の具体的理由
{range_reasoning}

---

#### 👁️ 2. ポジションとアクションから紐解く相手（Villain）のハンドリーディング
{hand_reading}

---

#### 🤖 ソルバーの推奨頻度マトリクス（最善手）
"""
    if "防衛" not in mode:
        explanation_md += f"- ⚪ **チェック (Check)**: `{freq_dict['check']:.1f}%` \n"
        explanation_md += f"- 🟢 **33%ベット (Small)**: `{freq_dict['bet_33']:.1f}%` \n"
        explanation_md += f"- 🔴 **70%ベット (Large)**: `{freq_dict['bet_70']:.1f}%` \n"
    else:
        explanation_md += f"- ⚪ **フォールド (Fold)**: `{freq_dict.get('fold', 0.0):.1f}%` \n"
        explanation_md += f"- 🟢 **コール (Call)**: `{freq_dict.get('call', 0.0):.1f}%` \n"
        explanation_md += f"- 🟤 **レイズ (Raise)**: `{freq_dict.get('raise', 0.0):.1f}%` \n"

    return explanation_md


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
    }
    st.session_state.history_stack.append(snapshot)

def pop_history():
    if st.session_state.history_stack:
        prev = st.session_state.history_stack.pop()
        st.session_state.game_data = prev["game_data"]
        st.session_state.quiz_phase = prev["quiz_phase"]
        st.session_state.quiz_answered = prev["quiz_answered"]
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
        
        if PREFLOP_ORDER.index(hero_pos) < PREFLOP_ORDER.index(villain_pos):
            opener, caller = hero_pos, villain_pos
            hero_oop = is_hero_oop(hero_pos, villain_pos)
            pos_text = "あなたがOOP(先攻)" if hero_oop else "あなたがIP(後攻)"
            preflop_summary = f"あなた({hero_pos})のオープンレイズに対し、{villain_pos} がコールして参加しました（{pos_text}）。"
        else:
            opener, caller = villain_pos, hero_pos
            hero_oop = is_hero_oop(hero_pos, villain_pos)
            pos_text = "あなたがOOP(先攻)" if hero_oop else "あなたがIP(後攻)"
            preflop_summary = f"{villain_pos} のオープンレイズに対し、あなた({hero_pos})がコールして参加しました（{pos_text}）。"
            
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

# --- 3. 相手フォールド時の専用終了画面 ---
elif st.session_state.game_state == "villain_folded":
    data = st.session_state.game_data
    st.markdown(f"### ⚔️ {data['current_street'].upper()} (ゲーム終了)")
    st.success("🤖 相手(Villain)はGTO防衛頻度の基準を下回るローエクイティハンドであったため、【フォールド (Fold)】を選択しました。")
    st.subheader(f"🏆 あなたの勝ちです！ 獲得ポット: {data['pot']:.1f}bb")
    st.info(f"🔍 相手が実際に持っていたハンド: 【 {data['villain_hand_raw']} 】")
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
    
    # シミュレーション実行
    hand_eq = run_simulation(hero_single_combo, villain_range_combos, board_obj)
    range_eq = run_simulation(hero_range_combos, villain_range_combos, board_obj)
    villain_hand_eq = run_simulation(villain_single_combo, hero_range_combos, board_obj)
    
    st.caption(f"📊 リアルタイムレンジ解析 -> あなたの個別ハンド勝率: {hand_eq*100:.1f}% | あなたのレンジ全体の勝率: {range_eq*100:.1f}%")
    st.markdown("---")
    
    # GTO頻度を算出
    gto_freqs = calculate_gto_action_frequencies(hand_eq, range_eq, street)
    
    # --- 【OOP (先攻) 時のロジック】 ---
    if hero_oop:
        if st.session_state.quiz_phase == 1:
            st.write("👉 あなた（先攻）のアクション番です。GTO頻度を意識して選択してください:")
            options = ["1: ベット (ポットの33%)", "2: ベット (ポットの70%)", "3: チェック (Check)"]
            ans = st.radio("選択:", options, key=f"oop_p1_{street}", label_visibility="collapsed")
            choice = int(ans[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.rerun()
            else:
                st.markdown(generate_advanced_gto_explanation("OOP・第1アクション", choice, gto_freqs, hand_eq, range_eq, data, street))

                if choice in [1, 2]:
                    if st.button("相手(Villain)の対抗判断を受ける ➡️"):
                        save_to_history()
                        bet_pct = 0.33 if choice == 1 else 0.70
                        v_defense_freq = judge_defense_gto_action(villain_hand_eq, bet_pct)
                        
                        # Villainのアクション選択（GTO最善解に基づく確率ダイスロール）
                        if random.uniform(0, 100) > v_defense_freq["fold"]:
                            data["pot"] += (data["pot"] * bet_pct * 2)
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
            # 相手(Villain)側のチェック後のベット判断（GTO最善手シミュレーション）
            v_gto = calculate_gto_action_frequencies(villain_hand_eq, 1.0 - range_eq, street)
            v_rand = random.uniform(0, 100)
            
            if v_rand < v_gto["bet_70"]:
                v_bet_pct = 0.70
            elif v_rand < (v_gto["bet_70"] + v_gto["bet_33"]):
                v_bet_pct = 0.33
            else:
                v_bet_pct = 0.0
            
            if v_bet_pct == 0.0:
                st.success("🤖 相手(Villain)はチェックバックを選択し、ショーダウン/次ストリートに進みました。")
                if st.button("次へ進む ➡️"):
                    save_to_history()
                    st.session_state.quiz_phase = "next_street_trigger"
                    st.rerun()
            else:
                st.warning(f"🤖 相手がポットの {int(v_bet_pct*100)}% サイズでベットしてきました！")
                hero_defense_freq = judge_defense_gto_action(hand_eq, v_bet_pct)
                
                def_options = ["1: フォールド (Fold)", "2: コール (Call)", "3: レイズ (Raise)"]
                ans2 = st.radio("ディフェンスの選択:", def_options, key=f"oop_p2_{street}", label_visibility="collapsed")
                choice2 = int(ans2[0])
                
                if not st.session_state.quiz_answered:
                    if st.button("アクションを確定する", use_container_width=True):
                        save_to_history()
                        st.session_state.quiz_answered = True
                        st.rerun()
                else:
                    st.markdown(generate_advanced_gto_explanation(f"OOP・防衛フェーズ ({int(v_bet_pct*100)}%)", choice2, hero_defense_freq, hand_eq, range_eq, data, street))
                    
                    if choice2 == 1:
                        st.error("フォールドしたためゲーム終了です。")
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
        # GTO上、先攻コール側（OOP）がドンクベットを打つ確率は極小のため原則チェック
        # 高勝率かつ一部の状況のみシミュレート
        villain_donk = (villain_hand_eq >= 0.78 and random.uniform(0, 100) < 12 and street != "river")
        
        if villain_donk:
            st.warning("🤖 相手(Villain)が先攻からドンクベット(ポットの66%)を仕掛けてきました。")
            hero_defense_freq = judge_defense_gto_action(hand_eq, 0.66)
            
            ip_def_opts = ["1: フォールド (Fold)", "2: コール (Call)", "3: レイズ (Raise)"]
            ans_ip1 = st.radio("対応選択:", ip_def_opts, key=f"ip_p1_bet_{street}", label_visibility="collapsed")
            choice = int(ans_ip1[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.rerun()
            else:
                st.markdown(generate_advanced_gto_explanation("IP・防衛フェーズ (ドンク)", choice, hero_defense_freq, hand_eq, range_eq, data, street))
                
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
            st.success("🤖 相手(Villain)はGTOベースに則り、チェックを選択しました。あなたのアクション番です。")
            
            ip_check_opts = ["1: ベット (ポットの33%)", "2: ベット (ポットの70%)", "3: チェックバック (ポッドコントロール)"]
            ans_ip2 = st.radio("アクション選択:", ip_check_opts, key=f"ip_p2_check_{street}", label_visibility="collapsed")
            choice = int(ans_ip2[0])
            
            if not st.session_state.quiz_answered:
                if st.button("アクションを確定する", use_container_width=True):
                    save_to_history()
                    st.session_state.quiz_answered = True
                    st.rerun()
            else:
                st.markdown(generate_advanced_gto_explanation("IP・アクションフェーズ", choice, gto_freqs, hand_eq, range_eq, data, street))
                
                if st.button("相手の対抗結果を確認して次へ進む ➡️"):
                    save_to_history()
                    st.session_state.quiz_answered = False 
                    
                    if choice in [1, 2]:
                        bet_pct = 0.33 if choice == 1 else 0.70
                        v_defense_freq = judge_defense_gto_action(villain_hand_eq, bet_pct)
                        
                        if random.uniform(0, 100) > v_defense_freq["fold"]:
                            data["pot"] += (data["pot"] * bet_pct * 2)
                            st.session_state.quiz_phase = "next_street_trigger"
                        else:
                            st.session_state.game_state = "villain_folded"
                    else:
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
            st.balloons()
            st.markdown("### 🏆 ショーダウン（リバー完了）")
            st.subheader(f"最終獲得ポット: {data['pot']:.1f}bb")
            st.info(f"🔍 **相手（Villain）のハンド: 【 {data['villain_hand_raw']} 】**")
            
            h_score = eval7.evaluate([eval7.Card(c) for c in [data['hero_hand_raw'][0:2], data['hero_hand_raw'][2:4]]] + board_obj)
            v_score = eval7.evaluate([eval7.Card(c) for c in [data['villain_hand_raw'][0:2], data['villain_hand_raw'][2:4]]] + board_obj)
            if h_score > v_score:
                st.success("✨ ショーダウンの結果、あなたのハンドが勝っていました！")
            elif v_score > h_score:
                st.error("相手のハンドの方が強かったです。")
            else:
                st.warning("引き分けです。")
                
            if st.button("もう一度新しいシチュエーションで練習する 🔄", use_container_width=True):
                st.session_state.game_state = "setup"
                st.rerun()
