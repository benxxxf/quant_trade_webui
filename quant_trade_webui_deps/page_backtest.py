from .py_loader import *
from .dataframe_plotter import *
from .ext_btstrategy import *
import streamlit as st
import backtrader as bt
import plotly.graph_objects as go
import pandas as pd


@st.fragment
def backtest_control_fragment():
    """
    回测用控件函数，使用st.fragment修饰防止每次修改就对全页面重新刷新耗时过高
    只有点击加载按钮后，才会rerun然后进入到backtest_chart_plot中输出回测结果
    """
    with st.sidebar:
        st.header("📁 上传策略脚本")
        uploaded_file_list = st.file_uploader(
            "上传 .py 策略脚本",
            type=["py"],
            help="请确保脚本中定义了继承自 ExtBtStrategy 的类",
            accept_multiple_files=True,
        )

        # 用户传入Backtrader策略，不过需要继承在bt.Strategy上拓展后的基类ExtBtStrategy
        # 该基类主要加了一些回测统计用的功能，从而和用户回测逻辑隔离开来
        if uploaded_file_list and (not st.session_state.strategy_dict):
            for uploaded_file in uploaded_file_list:
                file_content = uploaded_file.getvalue()
                file_name = uploaded_file.name
                module = load_user_module(file_content, file_name)
                if module:
                    st.session_state.strategy_dict |= extract_classes(
                        module, ExtBtStrategy, construt_flag=False
                    )
        # 多个策略文件加载后，选择单个策略运行
        if st.session_state.strategy_dict:
            selected_class_name = st.selectbox(
                "选择要运行的策略脚本", list(st.session_state.strategy_dict.keys())
            )
            selected_class = st.session_state.strategy_dict[selected_class_name][
                "class"
            ]

            if selected_class.__doc__:
                st.info(f"📖 策略说明: {selected_class.__doc__}")
            if st.button("🚀 加载", type="primary", width="stretch"):
                with st.spinner("正在加载策略..."):
                    st.session_state.current_strategy_class_name = selected_class_name

                st.success("✅ 策略加载完成！")
                st.rerun()  # 刷新页面显示图表
            if st.button("⏹️ 清空", type="secondary", width="stretch"):
                st.session_state.strategy_dict = {}
                st.session_state.current_strategy_class_name = None
                st.session_state.backtest_result = {}
                st.rerun()
        else:
            st.info("请上传您的策略文件(.py)")


@st.fragment
def backtest_mainboard_fragment():
    """
    回测用主面板配置界面
    使用st.fragment修饰防止每次修改就对全页面重新刷新耗时过高
    """

    # 构建了一个数据定义名(用户自定义的'上证指数'、'平安银行'之类的名字)和数据类名映射字典，方便后面快速查阅
    loaded_plotter_objname_classname_dict = {}
    if "plotter_dict" in st.session_state:
        for key, value in st.session_state.plotter_dict.items():
            if "obj" in value:
                loaded_plotter_objname_classname_dict[value["obj"].get_name()] = key
    if st.session_state.current_strategy_class_name is not None:
        st.write(f"当前运行策略:{st.session_state.current_strategy_class_name}")
        # 这里每个策略支持多数据源加载回测
        selected_plotter_names = st.multiselect(
            label="请选择要使用的数据源（至少选1个）",
            options=list(loaded_plotter_objname_classname_dict.keys()),
            help="按住 Ctrl 键可以选择多个数据源",
        )

        # 常用的回测设置，目前只定义了初始资金和佣金，后续有需求自行在此处添加
        with st.expander("💰 回测设置", expanded=True):
            initial_cash = st.number_input("初始资金", value=10000000.0, step=10000.0)
            commission = st.number_input(
                "佣金比例", value=0.001, step=0.0001, format="%.4f"
            )

        # 把此处一些其他地方要用到的配置信息放到st.session_state持久化之后，可以开始用start_backtest正式运行回测
        if st.button("🚀 执行回测", type="primary"):
            if len(selected_plotter_names) == 0:
                st.info("没有选择数据源，回测失败，请至少选择1个数据源！")
                st.stop()
            st.session_state.backtest_result["initial_cash"] = initial_cash
            st.session_state.backtest_result["commission"] = commission

            st.session_state.backtest_result["strategy_class_name"] = (
                st.session_state.current_strategy_class_name
            )
            st.session_state.backtest_result["selected_plotter_names"] = (
                selected_plotter_names
            )
            st.session_state.backtest_result[
                "loaded_plotter_objname_classname_dict"
            ] = loaded_plotter_objname_classname_dict
            start_backtest()


def start_backtest():
    """
    基于Backtrader的核心回测模块

    Returns:
        _type_: 无返回值
    """

    # 按照Backtrader官方Demo的标准回测写法
    cerebro = bt.Cerebro()
    selected_plotter_obj_list = []
    for plotter_name in st.session_state.backtest_result["selected_plotter_names"]:
        selected_plotter_class_name = st.session_state.backtest_result[
            "loaded_plotter_objname_classname_dict"
        ][plotter_name]
        origin_obj = st.session_state.plotter_dict[selected_plotter_class_name]["obj"]
        # 由于回测所用数据对象就是数据可视化页面的对象，修改会干扰原本数据可视化，因此这里用深拷贝隔离
        copied_plotter_obj = copy.deepcopy(origin_obj)
        cerebro.adddata(
            data=copied_plotter_obj.get_bt_data(),
            name=copied_plotter_obj.name,
        )
        selected_plotter_obj_list.append(copied_plotter_obj)

    # 动态添加用户脚本定义的策略，目前只支持单个Strategy类回测
    # selected_plotter_obj_list就是前面多数据源的列表构造传入，可以自行在策略中使用
    cerebro.addstrategy(
        st.session_state.strategy_dict[st.session_state.current_strategy_class_name][
            "class"
        ],
        selected_plotter_obj_list,
    )

    # 把配置信息中的内容加入到会测引擎
    cerebro.broker.setcash(st.session_state.backtest_result["initial_cash"])
    cerebro.broker.setcommission(
        commission=st.session_state.backtest_result["commission"]
    )

    # 添加回测结果常用分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturns")

    # 执行回测
    with st.spinner("回测运行中，请稍候..."):
        result = cerebro.run()
        final_value = cerebro.broker.getvalue()

    # 提取分析结果
    strat_result = result[0]
    sharpe = strat_result.analyzers.sharpe.get_analysis()
    returns = strat_result.analyzers.returns.get_analysis()
    drawdown = strat_result.analyzers.drawdown.get_analysis()
    # benchmark_returns = strat_result.analyzers.timereturn.get_analysis()
    trade_analysis = strat_result.analyzers.trades.get_analysis()

    returns_dict = strat_result.analyzers.timereturns.get_analysis()

    # 显示指标，包含如下八个：
    # 最终资产，总收益率，策略年化收益，市场基准收益，最大回撤
    # 夏普比率，交易次数，胜率，盈亏比
    # 这些结果都做了持久化，方便切换界面后依然能够在本界面查看
    st.session_state.backtest_result["final_value"] = final_value
    st.session_state.backtest_result["rnorm100"] = returns.get("rnorm100", "N/A")
    st.session_state.backtest_result["benchmark_return"] = benchmark_return = (
        selected_plotter_obj_list[0].get_ranged_df_benchmark_return()
    )
    st.session_state.backtest_result["draw_down"] = drawdown.max.drawdown
    st.session_state.backtest_result["sharperatio"] = sharpe.get("sharperatio", 0)

    total_closed = trade_analysis.total.closed
    won = trade_analysis.won.total
    lost = trade_analysis.lost.total
    win_rate = (won / total_closed) * 100 if total_closed else 0

    pnl_win = trade_analysis.won.pnl.average if won else 0
    pnl_lost = abs(trade_analysis.lost.pnl.average) if lost else 0
    profit_loss_ratio = pnl_win / pnl_lost if pnl_lost else 0

    st.session_state.backtest_result["total_closed"] = total_closed
    st.session_state.backtest_result["win_rate"] = win_rate
    st.session_state.backtest_result["profit_loss_ratio"] = profit_loss_ratio

    # 用于得到总资金变化曲线并显示出来
    returns_series = pd.Series(returns_dict)  # 将字典转换为 Series，索引为时间
    cumulative_return = (1 + returns_series).cumprod()
    portfolio_series = (
        st.session_state.backtest_result["initial_cash"] * cumulative_return
    )
    portfolio_series.name = "总资金额"
    st.session_state.backtest_result["portfolio_series"] = portfolio_series

    # 把ExtBtStrategy编写的每笔交易详细信息统计出来，后续用表格可视化
    trade_history_df = pd.DataFrame.from_dict(
        strat_result.trade_history, orient="index"
    ).reset_index(drop=True)
    name_grouped = trade_history_df.groupby("交易对象")
    grouped_trade_df_list = {}
    for name, group_df in name_grouped:
        new_group_df = group_df.set_index("交易时间", drop=False).sort_index(
            ascending=True
        )
        new_group_df["序号"] = range(1, len(new_group_df) + 1)
        grouped_trade_df_list[name] = new_group_df

    st.session_state.backtest_result["grouped_trade_history"] = grouped_trade_df_list

    # 这里是将所有涉及目标交易对象的每笔交易信息，在各自曲线上显示出来，
    # 会有一个红绿柱状图和折线，红绿柱状图代表交易股票变化，折线代表持仓股数变化
    # 由于是和K线及用户自定义的各种指标线在同一张图中，时间序列完全匹配，方便人工分析交易策略
    for it in selected_plotter_obj_list:
        for name, group_df in grouped_trade_df_list.items():
            if name == it.name:
                it.add_bar_to_plot(
                    group_df["交易股数"],
                    y_axis="y2",
                    colors_list=[
                        it.pos_color if v > 0 else it.neg_color
                        for v in group_df["交易股数"]
                    ],
                )
                merged_df = it.get_ranged_df().join(group_df, how="outer").sort_index()
                merged_df = merged_df.ffill()
                it.add_line_to_plot(
                    merged_df["剩余持仓"],
                    y_axis="y2",
                )

    st.session_state.backtest_result["backtest_plotter"] = selected_plotter_obj_list
    st.rerun()


def show_backtest_result():
    """
    用于显示回测结果

    Returns:
        _type_: 无返回
    """
    # 待检查回测结果参数清单
    result_to_check = [
        "strategy_class_name",
        "selected_plotter_names",
        "initial_cash",
        "commission",
        "final_value",
        "rnorm100",
        "benchmark_return",
        "draw_down",
        "sharperatio",
        "total_closed",
        "win_rate",
        "profit_loss_ratio",
        "portfolio_series",
        "grouped_trade_history",
        "backtest_plotter",
    ]
    if all(key in st.session_state.backtest_result for key in result_to_check):
        # 从st.session_state持久化区域取出回测结果，方便切换页面或其他一般交互后持续显示
        strategy_class_name = st.session_state.backtest_result["strategy_class_name"]
        selected_plotter_names = st.session_state.backtest_result[
            "selected_plotter_names"
        ]
        initial_cash = st.session_state.backtest_result["initial_cash"]
        commission = st.session_state.backtest_result["commission"]
        final_value = st.session_state.backtest_result["final_value"]
        rnorm100 = st.session_state.backtest_result["rnorm100"]
        benchmark_return = st.session_state.backtest_result["benchmark_return"]
        draw_down = st.session_state.backtest_result["draw_down"]
        sharperatio = st.session_state.backtest_result["sharperatio"]
        total_closed = st.session_state.backtest_result["total_closed"]
        win_rate = st.session_state.backtest_result["win_rate"]
        profit_loss_ratio = st.session_state.backtest_result["profit_loss_ratio"]

        portfolio_series = st.session_state.backtest_result["portfolio_series"]
        grouped_trade_history = st.session_state.backtest_result[
            "grouped_trade_history"
        ]
        backtest_plotter = st.session_state.backtest_result["backtest_plotter"]

        st.write(f"策略名：{strategy_class_name}")
        st.write(f"所用数据集：{selected_plotter_names}")
        st.write(f"初始资金：{initial_cash}元")
        st.write(f"佣金：{commission}")

        col_00, col_01, col_02, col_03 = st.columns(4)
        col_00.metric(
            "最终资产",
            f"{final_value:,.2f}元",
            delta=f"{((final_value/initial_cash)-1)*100:.2f}%",
            delta_color="inverse",
        )
        col_01.metric("策略年化收益率", f"{rnorm100:.2f}%")
        col_02.metric("无策略基准收益率", f"{benchmark_return*100:.2f}%")

        col_03.metric("最大回撤率", f"{draw_down:.2f}%")

        col_10, col_11, col_12, col_13 = st.columns(4)
        col_10.metric("夏普比率", f"{sharperatio:.3f}")

        col_11.metric("交易次数", f"{total_closed}")
        col_12.metric("盈利概率", f"{win_rate:.2f}%")
        col_13.metric("盈亏比", f"{profit_loss_ratio:.2f}")

        st.subheader("📈 回测可视化")

        # 查看总资金变化曲线
        st.write(f"{portfolio_series.name}曲线")
        st.line_chart(portfolio_series)

        st.write("分组交易明细")
        for name, group_trade_df in grouped_trade_history.items():
            st.dataframe(group_trade_df, width="stretch")

        st.write("用户定义K线数据")
        ind_cnt = 0

        # 把传入本策略的所有数据，在此处渲染，是基于数据查看器中的可视化部分加料版
        # 当然也可以构建一个专门的可视化类裁剪优化
        for it in backtest_plotter:
            st.plotly_chart(
                it.get_plotly_fig(),
                theme="streamlit",
                width="stretch",
                height="stretch",
                key=f"backtest_plotly_chart_{ind_cnt}",  # 固定 key，避免重复创建
            )
            ind_cnt += 1


def backtest_qtw_page():
    """
    策略回测功能页
    """
    if "strategy_dict" not in st.session_state:
        st.session_state.strategy_dict = {}

    if "current_strategy_class_name" not in st.session_state:
        st.session_state.current_strategy_class_name = None

    if "backtest_result" not in st.session_state:
        st.session_state.backtest_result = {}

    backtest_control_fragment()
    backtest_mainboard_fragment()
    show_backtest_result()
