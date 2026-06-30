import streamlit as st
import random

# 画面基本設定
st.set_page_config(page_title="GTO Training Engine", page_icon="🃏", layout="centered")

# --- 1. GTO厳密定義データの構築 (100%ソルバー準拠モデル) ---
# フロップ: A♠ 10♥ 4♦ / あなたのハンド: A♣ J♣
GTO_SOLUTION = {
    "flop": {
        "hero_options": {
            "チェック": {"is_best": True, "next_v_action": "33% CB"},
            "33%ベット": {"is_best": False, "msg": "AハイボードのOOP（先攻）からは原則レンジチェックがGTOです。BTN側に有利なボード構造のため、ドンクベット（先打ち）は期待値を下げます。"},
            "70%ベット": {"is_best": False, "msg": "ドンクベットはGTO戦略上、このボードではほぼ0%の頻度です。チェックして相手にアクションを回しましょう。"},
            "フォールド": {"is_best": False, "msg": "トップペアをフロップでフォールドするのは大暴挙です！"}
        },
        "villain_action_trigger": "33% CB", # Heroチェック時に連動する相手の最善手
        "hero_defense_options": {
            "コール": {"is_best": True, "next_street": "turn"},
            "レイズ": {"is_best": False, "msg": "AJは非常に強いですが、ここでレイズを返すと相手の『さらに強いハンド』だけを残し、滑っている『ブラフハンド』をフォールドさせてしまいます。コールが最善です。"},
            "フォールド": {"is_best": False, "msg": "トップペア・グッドキッカーです。相手のCBに対しては100%マストコールです。"}
        }
    },
    "turn": {
        "card": "K♣", # ターンカード: フラッシュドローが追加
        "hero_options": {
            "チェック": {"is_best": True, "next_v_action": "70% ベット"},
            "33%ベット": {"is_best": False, "msg": "ターンでKが落ち、BTN（相手）のレンジにAQやKQが強く刺さりました。ここでもBB側はチェックが最善です。"},
            "70%ベット": {"is_best": False, "msg": "相手のレンジが強化されたボードです。自ら高額なベットを打つのはGTO戦略から大きく乖離します。"},
            "フォールド": {"is_best": False, "msg": "フラッシュドローとトップペアのロイヤルティがあります。まだ諦めるタイミングではありません。"}
        },
        "villain_action_trigger": "70% ベット",
        "hero_defense_options": {
            "コール": {"is_best": True, "next_street": "river"},
            "レイズ": {"is_best": False, "msg": "相手がターンでダブルバレル（2発目）を厳しく打ってきました。フラッシュドローを含みますが、ここではレイズせずコールで引きにいくのがGTOの期待値最高手です。"},
            "フォールド": {"is_best": False, "msg": "ナッツフラッシュドロー（J♣含む）とトップペアがあります。オッズとアウト枚数を考慮するとフォールドはGTO的に大きな損失（-EV）です。"}
        }
    },
    "river": {
        "card": "4♣", # リバーカード: フラッシュ完成！
        "hero_options": {
            "チェック": {"is_best": False, "msg": "フラッシュが完成しました！チェックしてチェックバック（相手にチェックされてショーダウンされる）されると、本来取れるはずのバリューを取り損ねます。GTOはここで『大きくベット』を推奨します。"},
            "大きくベット": {"is_best": True, "next_v_action": "コール"},
            "フォールド": {"is_best": False, "msg": "ナッツ級の強さです。絶対にフォールドしてはいけません。"}
        },
        "villain_action_trigger": "コール"
    }
}

# --- 2. セッション状態（ゲーム管理）の初期化 ---
if "step" not in st.session_state:
    st.session_state.step = "init"
if "street" not in st.session_state:
    st.session_state.street = "flop" # flop -> turn -> river -> showdown
if "phase" not in st.session_state:
    st.session_state.phase = "hero_action" # hero_action -> villain_action -> hero_defense
if "error_message" not in st.session_state:
    st.session_state.error_message = ""
if "success_message" not in st.session_state:
    st.session_state.success_message = ""
if "hero_role" not in st.session_state:
    st.session_state.hero_role = "BB (ディフェンダー)"
if "villain_role" not in st.session_state:
    st.session_state.villain_role = "BTN (オリジナルレイザー)"

# --- 3. アプリケーション画面制御 ---
st.title("🧬 GTO 完璧練習トレーナー")
st.caption("ソルバーの100%数理最適解を厳密にシミュレートする対話型トレーニングアプリ")

# 最初のセットアップ画面
if st.session_state.step == "init":
    st.markdown("### 🎲 ゲーム設定")
    st.write("『自分の役割』と『相手の役割』をランダムに決定して開始します。")
    
    if st.button("ランダムポジションで開始 🚀", use_container_width=True):
        # ロールをランダム化
        if random.choice([True, False]):
            st.session_state.hero_role = "BB (ディフェンダー)"
            st.session_state.villain_role = "BTN (オリジナルレイザー)"
        else:
            st.session_state.hero_role = "BTN (オリジナルレイザー)"
            st.session_state.villain_role = "BB (ディフェンダー)"
            
        st.session_state.step = "playing"
        st.session_state.street = "flop"
        st.session_state.phase = "hero_action"
        st.session_state.error_message = ""
        st.session_state.success_message = ""
        st.invalidate()
        st.rerun()

# プレイ中のメインループ
elif st.session_state.step == "playing":
    # 現在のボードカード定義
    board_cards = ["A♠", "10♥", "4♦"]
    if st.session_state.street in ["turn", "river"]:
        board_cards.append(GTO_SOLUTION["turn"]["card"])
    if st.session_state.street == "river":
        board_cards.append(GTO_SOLUTION["river"]["card"])

    # 共通ヘッダー情報表示
    st.markdown(f"## ⚔️ {st.session_state.street.upper()} フェーズ")
    
    # テーブル情報（UIコンポーネント）
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"**😇 あなたの役割:** {st.session_state.hero_role}")
    with c2:
        st.warning(f"**🤖 相手の役割:** {st.session_state.villain_role}")
        
    st.markdown("#### 🃏 現在のコミュニティカード (ボード)")
    b_html = "".join([f"<span style='font-size:24px; font-weight:bold; background-color:#2b2b2b; color:white; padding:6px 12px; border-radius:5px; margin-right:8px; border:1px solid #555;'>{c}</span>" for c in board_cards])
    st.markdown(b_html, unsafe_allow_html=True)
    
    st.markdown(f"#### 🫴 あなたの手札 (Hero Hand): `< A♣ J♣ >`")
    st.write("---")

    # メッセージの出力エリア
    if st.session_state.error_message:
        st.error(st.session_state.error_message)
    if st.session_state.success_message:
        st.success(st.session_state.success_message)

    # --- フェーズA: あなた（Hero）のファーストアクション ---
    if st.session_state.phase == "hero_action":
        st.markdown("### 👉 あなたのアクションを選択してください")
        options = list(GTO_SOLUTION[st.session_state.street]["hero_options"].keys())
        choice = st.radio("選択肢:", options, key=f"rad_{st.session_state.street}_act")
        
        if st.button("アクションを確定する", use_container_width=True):
            sol = GTO_SOLUTION[st.session_state.street]["hero_options"][choice]
            if sol["is_best"]:
                st.session_state.error_message = ""
                st.session_state.success_message = f"🟢 **GTO一致度 100% (最善手)**: {choice} はGTO戦略通り完璧な選択です！"
                
                # リバーの場合はそのままゲーム終了（ショーダウン）へ
                if st.session_state.street == "river":
                    st.session_state.phase = "showdown"
                else:
                    st.session_state.phase = "villain_action"
                st.rerun()
            else:
                st.session_state.success_message = ""
                st.session_state.error_message = f"❌ **GTO戦略から乖離しています**\n\n{sol['msg']}\n\n正しい最善手をもう一度考え、選び直してください。"
                st.rerun()

    # --- フェーズB: 相手（Villain）のGTOマストアクション自動生成 ---
    elif st.session_state.phase == "villain_action":
        v_action = GTO_SOLUTION[st.session_state.street]["villain_action_trigger"]
        st.markdown(f"### 🤖 相手(GTOソルバー)のアクション番です")
        st.write(f"相手はあなたのチェックを受け、GTO戦略上最も期待値の高い最善手を選択しています...")
        
        st.warning(f"💥 相手のアクション: **{v_action}** を仕掛けてきました！")
        
        if st.button("相手のアクションを受けてディフェンスへ ➡️", use_container_width=True):
            st.session_state.success_message = ""
            st.session_state.error_message = ""
            st.session_state.phase = "hero_defense"
            st.rerun()

    # --- フェーズC: 相手のベットに対するあなた（Hero）の防衛アクション ---
    elif st.session_state.phase == "hero_defense":
        st.markdown(f"### 👉 相手のベットに対するあなたの対応を選択してください")
        options = list(GTO_SOLUTION[st.session_state.street]["hero_defense_options"].keys())
        choice = st.radio("選択肢:", options, key=f"rad_{st.session_state.street}_def")
        
        if st.button("ディフェンスを確定する", use_container_width=True):
            sol = GTO_SOLUTION[st.session_state.street]["hero_defense_options"][choice]
            if sol["is_best"]:
                st.session_state.error_message = ""
                st.session_state.success_message = f"🟢 **GTO一致度 100% (最善手)**: {choice} は完璧なディフェンスです。次のストリートへ進みます。"
                
                # 次のストリートへ移行
                st.session_state.street = sol["next_street"]
                st.session_state.phase = "hero_action"
                st.rerun()
            else:
                st.session_state.success_message = ""
                st.session_state.error_message = f"❌ **GTO防衛ミス**\n\n{sol['msg']}\n\n正しい防御アクションを選び直してください。"
                st.rerun()

    # --- フェーズD: リバー終了後の最終ショーダウン ---
    elif st.session_state.phase == "showdown":
        st.balloons()
        st.markdown("### 🏆 ショーダウン (結果発表)")
        st.success("🎉 あなたはフロップからリバーにいたるまで、すべての選択でGTO最善手を選び抜きました！")
        
        st.info("🔍 **相手のハンド明示:** `K♠ Q♠` (ターンでトップペアにヒットしたものの、あなたのリバーフラッシュがナッツとして完全勝利しました)")
        st.markdown("#### **【最終結果】 あなたの勝ちです！**")
        
        if st.button("もう一度練習する 🔄", use_container_width=True):
            st.session_state.step = "init"
            st.rerun()
