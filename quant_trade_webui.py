from quant_trade_webui_deps import *


# 本项目主程序
def run_quant_trade_webui():
    # 初始化日志部分的session_state
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "logger_instance" not in st.session_state:
        st.session_state.logger_instance = StreamlitLogger()
    if "is_capturing" not in st.session_state:
        st.session_state.is_capturing = False

    # 替换日志捕获
    if not st.session_state.is_capturing:
        sys.stdout = st.session_state.logger_instance
        st.session_state.is_capturing = True
    st.set_page_config(layout="wide")
    # 配置顶部页面导航，每个导航页对应一个功能模块
    pg = st.navigation(
        [
            st.Page(
                database_manager_qtw_page, title="数据库管理", icon=":material/folder:"
            ),
            st.Page(data_viz_qtw_page, title="数据可视化", icon=":material/bar_chart:"),
            st.Page(backtest_qtw_page, title="策略回测", icon=":material/timeline:"),
        ],
        position="top",
    )

    pg.run()  # 根据导航按钮运行特定页面
    st.divider()

    # 使用 st.expander 可以让用户选择展开或收起日志框，节省空间
    with st.expander("📜 运行日志 (点击展开/收起)", expanded=False):
        log_text = (
            "\n".join(st.session_state.logs) if st.session_state.logs else "暂无日志..."
        )
        st.code(log_text, language="bash")


if __name__ == "__main__":
    run_quant_trade_webui()
