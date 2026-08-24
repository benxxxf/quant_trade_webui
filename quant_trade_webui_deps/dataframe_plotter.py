from .common_utils import *
import plotly.graph_objects as go
from .database_csmar_zip_parser import *
import backtrader as bt
import datetime
import pandas as pd
import numpy as np


class WindowMethodType(Enum):
    """
    窗口值计算类型枚举
    """

    MAX_METHOD = "最大值"
    MIN_METHOD = "最小值"
    AVG_METHOD = "平均值"
    STD_METHOD = "标准差"


class WeightAllocationType(Enum):
    """
    窗口加权类型枚举
    """

    SMA = "等权重平均"
    EMA = "指数移动平均"


class PlotType(Enum):
    """
    绘图类型枚举
    之前代码用上了，目前已废弃
    """

    CANDLESTICK = "K线"
    LINE = "折线"
    BAR = "柱状"
    TRIANGLE = "三角形"


class DataFramePlotter:
    """
    数据绘制器基类
    用户自定义的数据绘制类，都要继承此类
    """

    def __init__(
        self,
        name: str,
        df: pd.DataFrame,
        open_col: str,
        high_col: str,
        low_col: str,
        close_col: str,
        time_start: str,
        time_end: str,
    ):
        """
        数据绘制器基类构造函数

                Args:
                    name (str): 数据绘制器名
                    df (pd.DataFrame): 数据绘制器完整数据
                    open_col (str): 开盘价列名
                    high_col (str): 最高价列名
                    low_col (str): 最低价列名
                    close_col (str): 收盘价列名
                    time_start (str): 目标数据起始时间戳，支持时间格式如下所示，也可以取""，表示从1970-01-01 00:00:00开始
                    time_end (str): 目标数据终止时间戳，支持时间格式如下所示，也可以取""，表示到当前时刻终止

        支持的时间格式：
                '%Y-%m-%d',           # 2024-01-01
                '%Y-%m-%d %H:%M:%S',  # 2024-01-01 00:00:00
                '%Y/%m/%d',           # 2024/01/01
                '%Y%m%d',             # 20240101
                '%Y-%m-%dT%H:%M:%S',  # 2024-01-01T00:00:00
                '%d-%m-%Y',           # 01-01-2024
                '%d/%m/%Y',           # 01/01/2024
                '%Y年%m月%d日',        # 2024年01月01日
        """
        self.df = df
        self.name = name

        # 这里的ranged_dfs就是从完整数据中截取出来的目标数据
        self.ranged_dfs = filter_dfs_by_time_range(
            df=df,
            date_start=time_start,
            date_end=time_end,
        )
        # Plotly绘图器，后续所有绘图操作都是基于该对象增加
        self.fig = go.Figure()
        self.open_col = open_col
        self.high_col = high_col
        self.low_col = low_col
        self.close_col = close_col
        if time_start != "":
            self.time_start_stamp = parse_date_flexible(time_start)

        else:
            self.time_start_stamp = pd.Timestamp("1970-01-01 00:00:00")

        if time_end != "":
            self.time_end_stamp = parse_date_flexible(time_end)
        else:
            self.time_end_stamp = pd.Timestamp.now()
        self.time_start_str = self.time_start_stamp.strftime("%Y-%m-%d %H:%M:%S")
        self.time_end_str = self.time_end_stamp.strftime("%Y-%m-%d %H:%M:%S")

        # 将数据绘制器和Backtrader的加载数据类型进行映射
        self.bt_data = bt.feeds.PandasData(
            dataname=self.df,
            open=self.open_col,
            high=self.high_col,
            low=self.low_col,
            close=self.close_col,
            fromdate=self.time_start_stamp,
            todate=self.time_end_stamp,
        )

        self.plotly_fig_init()
        self.pos_color = "red"
        self.neg_color = "green"

        # 默认在fig上先增加K线图
        self.add_candlestick_to_plot(name=f"{self.name}主K线")

    # 基于Plotly的金融界面布局初始化，可按需调整
    def plotly_fig_init(self):
        """
        初始化Plotly金融图表的布局和公共显示配置。

        Returns:
            None: 初始化绘图器内部状态和图表布局。
        """
        self.init_3dsurface_plot = False
        self.init_slider_plot = False
        self.init_timevarying_line = False
        self.y_cut_line_pos = 0.3
        self.plot_spacing = 0.03
        self.x_cut_line_pos = 0.8
        self.button_bottom_y_pos = self.y_cut_line_pos + self.plot_spacing
        self.slider_bottom_y_pos = self.y_cut_line_pos + self.plot_spacing * 3
        self.fig = go.Figure()
        self.auto_xaxis = {"y": "x", "y2": "x", "y3": "x3"}
        # 设置主图x和y的网格区域
        self.fig.update_layout(
            xaxis=dict(
                domain=[0, self.x_cut_line_pos - self.plot_spacing / 2],
                fixedrange=False,
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikecolor="gray",
                spikethickness=1,
                rangeslider=dict(visible=False),
                hoverformat="%Y-%m-%d %H:%M:%S",
            ),
            yaxis=dict(
                domain=[self.y_cut_line_pos + self.plot_spacing / 2, 1.0],
                fixedrange=False,
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikecolor="gray",
                spikethickness=1,
                anchor="x",
            ),
            yaxis2=dict(
                domain=[0.0, self.y_cut_line_pos - self.plot_spacing / 2],
                fixedrange=False,
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikecolor="gray",
                spikethickness=1,
                anchor="x",
            ),
            xaxis3=dict(
                domain=[self.x_cut_line_pos + self.plot_spacing / 2, 1.0],
                anchor="y3",
                fixedrange=False,
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikecolor="gray",
                spikethickness=1,
                rangeslider=dict(visible=False),
                hoverformat="%Y-%m-%d %H:%M:%S",
            ),
            yaxis3=dict(
                domain=[0, self.y_cut_line_pos - self.plot_spacing / 2],
                anchor="x3",
                fixedrange=False,
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikecolor="gray",
                spikethickness=1,
            ),
        )

        # 公共配置
        self.fig.update_layout(
            hovermode="x unified",
            # 图例设置
            showlegend=True,
            legend=dict(
                x=1.0,
                y=1.0,
                bgcolor="rgba(255, 255, 255, 0.8)",  # 半透明背景，避免遮挡
                bordercolor="Black",
                xanchor="right",
                yanchor="top",
                borderwidth=1,
                font=dict(size=12),
            ),
            # 移除默认边距，充分利用空间
            margin=dict(l=5, r=5, t=25, b=5),
        )
        # 这里可根据需求调整曲线上数字显示格式
        # self.fig.update_yaxes(tickformat=".8e")

    # 一些常用的读取内部变量接口
    def get_bt_data(self):
        """
        获取Backtrader使用的数据源对象。

        Returns:
            bt.feeds.PandasData: Backtrader Pandas数据源。
        """
        return self.bt_data

    def get_plotly_fig(self):
        """
        获取当前Plotly图表对象。

        Returns:
            go.Figure: 当前绘图器维护的Plotly图表。
        """
        return self.fig

    def get_main_df(self):
        """
        获取完整的原始数据表。

        Returns:
            pd.DataFrame: 绘图器初始化时传入的完整数据。
        """
        return self.df

    def get_ranged_df(self):
        """
        获取按目标时间范围截取后的数据表。

        Returns:
            pd.DataFrame: 当前时间范围内的数据。
        """
        return self.ranged_dfs

    def get_name(self):
        """
        获取数据绘制器名称。

        Returns:
            str: 数据绘制器名称。
        """
        return self.name

    def get_ranged_df_benchmark_return(self):
        """
        获取目标数据的总收益率

        Returns:
            float32: 总收益率
        """
        benchmark_return = (
            self.ranged_dfs[self.close_col].iloc[-1]
            / self.ranged_dfs[self.close_col].iloc[0]
            - 1
        )
        return benchmark_return

    # 把外部处理的series更新到ranged_df上
    def update_series_to_ranged_df(self, series: pd.Series):
        """
        把外部处理的series更新到ranged_df上
        Args:
            series (pd.Series): 外部的series，需注意时间序列要和ranged_dfs匹配，且必须有name属性

        Raises:
            ValueError: 无name属性报错
        """
        if series.name:
            self.ranged_dfs[series.name] = series.copy()
        else:
            raise ValueError("Updated series to ranged df should has 'name'!")

    def add_candlestick_to_plot(self, name: str, y_axis: str = "y"):
        """
        给fig追加K线图

        Args:
            name (str): K线图名
            y_axis (str, optional): K线放哪个轴，支持'y','y2','y3'. 默认'y',即面积最大的主图区域
        """

        self.fig.add_trace(
            go.Candlestick(
                x=self.ranged_dfs.index,
                open=self.ranged_dfs[self.open_col],
                high=self.ranged_dfs[self.high_col],
                low=self.ranged_dfs[self.low_col],
                close=self.ranged_dfs[self.close_col],
                increasing=dict(
                    line=dict(color=self.pos_color, width=0.5), fillcolor=self.pos_color
                ),
                decreasing=dict(
                    line=dict(color=self.neg_color, width=0.5), fillcolor=self.neg_color
                ),
                line=dict(width=0.5),
                whiskerwidth=1,
                name=name,
                xaxis=self.auto_xaxis[y_axis],
                yaxis=y_axis,
            ),
        )

    def add_line_to_plot(self, series: pd.Series, y_axis: str):
        """
        给fig追加曲线

        Args:
            series (pd.Series): 待绘线的series，索引要是时间序列，且有name名字
            y_axis (str): 放哪个轴，支持'y','y2','y3'
        """
        self.fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series,
                mode="lines",
                name=series.name,
                line=dict(color=string_to_rgb(series.name), width=1),
                xaxis=self.auto_xaxis[y_axis],
                yaxis=y_axis,
            ),
        )

    def add_bar_to_plot(
        self, series: pd.Series, y_axis: str = "y2", colors_list: list = []
    ):
        """
        给fig追加柱状图

        Args:
            series (pd.Series): 待绘线的series，索引要是时间序列，且有name名字
            y_axis (str): 放哪个轴，支持'y','y2','y3'
            color_list (list): 柱状图颜色列表，如无配置则默认采用self.pos_color配色
        """
        if not colors_list:
            colors_list = self.pos_color
        self.fig.add_trace(
            go.Bar(
                x=series.index,
                y=series,
                name=series.name,
                marker=dict(color=colors_list),
                opacity=1.0,
                xaxis=self.auto_xaxis[y_axis],
                yaxis=y_axis,
            ),
        )

    def add_point_to_plot(
        self, series: pd.Series, y_axis: str, colors_list=[], symbols_list=[]
    ):
        """
        给fig追加散点

        Args:
            series (pd.Series): 待绘线的series，索引要是时间序列，且有name名字
            y_axis (str): 放哪个轴，支持'y','y2','y3'
            color_list (list): 散点颜色列表，如无配置则默认采用self.pos_color配色
            symbol_list (list): 散点形状列表，如无配置则默认采用上三角形
        """
        if not colors_list:
            colors_list = self.pos_color
        if not symbols_list:
            symbols_list = "triangle-up"
        self.fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series,
                mode="markers",
                marker=dict(
                    symbol=symbols_list,
                    size=12,
                    color=colors_list,
                ),
                name=series.name,
                showlegend=True,
                xaxis=self.auto_xaxis[y_axis],
                yaxis=y_axis,
                text=series.astype(str),
            ),
        )

    def find_trace_index_by_name(self, trace_name):
        """
        根据fig的trade名得到trace索引

        Args:
            trace_name (_type_): trace名

        Returns:
            _type_: trace索引
        """
        for idx, trace in enumerate(self.fig.data):
            if trace.name == trace_name:
                return idx
        return None

    def add_dynamic_bar_to_plot(
        self,
        name,
        time_index: pd.DatetimeIndex,
        price_center_array: np.ndarray,
        chip_2d_array: np.ndarray,
        threholds_value_array: np.ndarray,
        greater_pos_color_flag: bool,
    ):
        """
        给fig追加时变柱状图，目前用于时变筹码分布估算

        Args:
            name (_type_): 柱状图名字
            time_index (pd.DatetimeIndex): 时间序列，长M的一维数组
            price_center_array (np.ndarray): 柱状图的价位中心值信息，长N的一维数组
            chip_2d_array (np.ndarray): (MxN)的2维筹码分布，M是时间，N是筹码组数
            threholds_value_array (np.ndarray): 颜色参考阈值，长M的一维数组
            greater_pos_color_flag (bool): 每个筹码大于阈值则用pos_color的布尔量，根据布尔真假来正反向取色
        """
        n_days = len(time_index)
        percent_price_center, percent_daily_chip = get_available_chips_by_percent(
            price_center_array, chip_2d_array[0][:]
        )
        if greater_pos_color_flag == True:
            first_color_list = [
                self.pos_color if val > threholds_value_array[0] else self.neg_color
                for val in percent_price_center
            ]
        else:
            first_color_list = [
                self.neg_color if val > threholds_value_array[0] else self.pos_color
                for val in percent_price_center
            ]
        self.fig.add_trace(
            go.Bar(
                x=percent_price_center,
                y=percent_daily_chip,
                name=name,
                marker=dict(
                    color=first_color_list,
                    colorscale="Viridis",
                ),
                xaxis="x3",
                yaxis="y3",
            ),
        )
        CHIP_INDEX = self.find_trace_index_by_name(trace_name=name)
        if self.init_slider_plot == False:
            self.fig.add_shape(
                type="line",
                x0=time_index[0],
                y0=0,
                x1=time_index[0],
                y1=1,
                yref="paper",
                line=dict(color="black", width=1, dash="dash"),
                layer="above",
            )
            dropdown_buttons = []
            for i in range(n_days):
                percent_price_center, percent_daily_chip = (
                    get_available_chips_by_percent(
                        price_center_array, chip_2d_array[i][:]
                    )
                )
                if greater_pos_color_flag == True:
                    color_list = [
                        (
                            self.pos_color
                            if val > threholds_value_array[i]
                            else self.neg_color
                        )
                        for val in percent_price_center
                    ]
                else:
                    color_list = [
                        (
                            self.neg_color
                            if val > threholds_value_array[i]
                            else self.pos_color
                        )
                        for val in percent_price_center
                    ]
                update_dict = dict(
                    method="update",
                    args=[
                        {
                            "y": percent_daily_chip,
                            "x": percent_price_center,
                            "marker": {
                                "color": color_list,
                            },
                        },  # 更新筹码图的 y 值
                        {  # 更新布局（竖线位置）
                            "shapes[0].x0": time_index[i],
                            "shapes[0].x1": time_index[i],
                            "transition": {"duration": 0},
                        },
                        [CHIP_INDEX],  # 只更新索引为 CHIP_INDEX 的 trace
                    ],
                    label=time_index[i].strftime("%Y-%m-%d %H:%M:%S"),
                    # str(np.datetime_as_string(time_index[i], unit="D")),
                )
                dropdown_buttons.append(update_dict)
            self.fig.update_layout(
                template="plotly_white",
                updatemenus=[
                    dict(
                        type="dropdown",  # 改为下拉菜单
                        direction="down",
                        buttons=dropdown_buttons,
                        showactive=True,
                        x=0.0,
                        y=1.0,
                        xanchor="left",
                        yanchor="top",
                    )
                ],
            )
            self.init_slider_plot = True

    @abstractmethod
    def create_fig(self) -> go.Figure:
        """预处理：子类必须实现"""
        pass


def get_window_value(
    series: pd.Series,
    window_len: int,
    method_type: WindowMethodType,
    weight_allocation: WeightAllocationType = WeightAllocationType.SMA,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    计算窗口值
    注意:series传完整序列，再在filter_date_start和filter_date_end给出目标时间范围，可以保证目标序列初始无NaN数值

    Args:
        series (pd.Series): 待计算series数组
        window_len (int): 窗口长度
        method_type (WindowMethodType): 窗口计算方法
        weight_allocation (WeightAllocationType, optional): 窗口权重方式. 默认平均加权
        filter_date_start (str, optional): 目标序列起始时间
        filter_date_end (str, optional): 目标序列终止时间

    Returns:
        pd.Series: 窗口计算完成的目标序列
    """

    if method_type == WindowMethodType.MAX_METHOD:
        if weight_allocation == WeightAllocationType.SMA:
            window_series = series.rolling(window=window_len).max()
        else:
            raise ValueError(f"MAX METHOD not support EMA!")
    elif method_type == WindowMethodType.MIN_METHOD:
        if weight_allocation == WeightAllocationType.SMA:
            window_series = series.rolling(window=window_len).min()
        else:
            raise ValueError(f"MIN METHOD not support EMA!")
    elif method_type == WindowMethodType.AVG_METHOD:
        if weight_allocation == WeightAllocationType.SMA:
            window_series = series.rolling(window=window_len).mean()
        elif weight_allocation == WeightAllocationType.EMA:
            window_series = series.ewm(span=window_len, adjust=True).mean()
        else:
            raise ValueError(
                f"AVG METHOD not support weight allocation type '{weight_allocation}'!"
            )
    elif method_type == WindowMethodType.STD_METHOD:
        if weight_allocation == WeightAllocationType.SMA:
            window_series = series.rolling(window=window_len).std()
        elif weight_allocation == WeightAllocationType.EMA:
            window_series = series.ewm(span=window_len, adjust=True).std()
        else:
            raise ValueError(
                f"STD METHOD not support weight allocation type '{weight_allocation}'!"
            )
    else:
        raise ValueError(f"Unsupport method type {method_type}")
    time_filtered_series = filter_dfs_by_time_range(
        df=window_series, date_start=filter_date_start, date_end=filter_date_end
    )
    time_str = infer_time_unit(series.index)
    series_name = f"{window_len}{time_str}{series.name}{method_type.value}"
    time_filtered_series.name = series_name

    return time_filtered_series


def get_rsi(
    series: pd.Series,
    window_len: int,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    计算RSI指标

    Args:
        series (pd.Series): 待计算series数组
        window_len (int): 窗口长度
        filter_date_start (str, optional): 目标起始时间
        filter_date_end (str, optional): 目标终止时间

    Returns:
        pd.Series: 目标时间范围的RSI指标
    """
    rsi_array = talib.RSI(series.values.astype(float), window_len)
    time_str = infer_time_unit(series.index)
    rsi_series_name = f"{window_len}{time_str}RSI"
    rsi_series = pd.Series(rsi_array, index=series.index, name=rsi_series_name)
    time_filtered_series = filter_dfs_by_time_range(
        df=rsi_series, date_start=filter_date_start, date_end=filter_date_end
    )

    return time_filtered_series


def get_macd(
    series: pd.Series,
    fast_period=12,
    slow_period=26,
    signal_period=9,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    计算MACD

    Args:
        series (pd.Series): 待计算series数组
        fast_period (int, optional): 快周期，默认12.
        slow_period (int, optional): 慢周期，默认26
        signal_period (int, optional): 信号周期，默认9
        filter_date_start (str, optional): 目标起始时间
        filter_date_end (str, optional): 目标终止时间

    Returns:
        (pd.Series,pd.Series,pd.Series): DIF,DEA,MACD
    """
    dif_array, dea_array, macd_array = talib.MACD(
        series,
        fastperiod=fast_period,
        slowperiod=slow_period,
        signalperiod=signal_period,
    )
    dif_series = pd.Series(dif_array, index=series.index, name="DIF")
    dea_series = pd.Series(dea_array, index=series.index, name="DEA")
    macd_series = pd.Series(macd_array, index=series.index, name="MACD")
    time_filtered_series_list = filter_dfs_by_time_range(
        df=[dif_series, dea_series, macd_series],
        date_start=filter_date_start,
        date_end=filter_date_end,
    )
    return (
        time_filtered_series_list[0],
        time_filtered_series_list[1],
        time_filtered_series_list[2],
    )


def get_future_return_point(
    series: pd.Series,
    return_rate_threshold: float,
    time_len: int,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    获取未来指定周期内绝对收益率超过阈值的数据点。

    Args:
        series (pd.Series): 待计算的价格或数值序列。
        return_rate_threshold (float): 绝对收益率筛选阈值。
        time_len (int): 向前观察的周期长度。
        filter_date_start (str, optional): 目标序列起始时间。
        filter_date_end (str, optional): 目标序列终止时间。

    Returns:
        pd.Series: 满足收益率阈值条件的数据点及其未来收益率。
    """
    future_return_series = series.shift(-1 * time_len) / series - 1
    time_filtered_series = filter_dfs_by_time_range(
        df=future_return_series, date_start=filter_date_start, date_end=filter_date_end
    )
    point_series = time_filtered_series[
        abs(time_filtered_series) > return_rate_threshold
    ]
    return point_series


def get_return_rate(
    series: pd.Series,
    time_len: int,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    计算指定周期的历史收益率。

    Args:
        series (pd.Series): 待计算的价格或数值序列。
        time_len (int): 收益率计算周期长度。
        filter_date_start (str, optional): 目标序列起始时间。
        filter_date_end (str, optional): 目标序列终止时间。

    Returns:
        pd.Series: 目标时间范围内的收益率序列。
    """
    return_rate_series = series / series.shift(time_len) - 1
    time_filtered_series = filter_dfs_by_time_range(
        df=return_rate_series, date_start=filter_date_start, date_end=filter_date_end
    )
    return time_filtered_series


def get_bias_rate(
    series: pd.Series,
    time_len: int,
    weight_allocation=WeightAllocationType.SMA,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    计算价格相对于窗口值的乖离率。

    Args:
        series (pd.Series): 待计算的价格或数值序列。
        time_len (int): 窗口长度。
        weight_allocation (WeightAllocationType, optional): 窗口权重方式，默认等权重平均。
        filter_date_start (str, optional): 目标序列起始时间。
        filter_date_end (str, optional): 目标序列终止时间。

    Returns:
        pd.Series: 目标时间范围内的价格乖离率序列。
    """
    window_series = get_window_value(
        series=series,
        window_len=time_len,
        method_type=weight_allocation,
        filter_date_start=filter_date_start,
        filter_date_end=filter_date_end,
    )
    time_filtered_series = filter_dfs_by_time_range(
        df=series, date_start=filter_date_start, date_end=filter_date_end
    )
    time_unit = infer_time_unit(series.index)
    bias_name = f"{time_len}{time_unit}价格乖离率"
    bias_series = (time_filtered_series - window_series) / time_filtered_series
    bias_series.name = bias_name
    return bias_series


def get_adx(
    high_series: pd.Series,
    low_series: pd.Series,
    close_series: pd.Series,
    window_len: int,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    根据最高价、最低价和收盘价计算ADX指标。

    Args:
        high_series (pd.Series): 最高价序列。
        low_series (pd.Series): 最低价序列。
        close_series (pd.Series): 收盘价序列。
        window_len (int): ADX计算周期长度。
        filter_date_start (str, optional): 目标序列起始时间。
        filter_date_end (str, optional): 目标序列终止时间。

    Returns:
        pd.Series: 目标时间范围内的ADX指标序列。
    """
    adx_array = talib.ADX(
        high=high_series.values.astype(float),
        low=low_series.values.astype(float),
        close=close_series.values.astype(float),
        timeperiod=window_len,
    )
    time_str = infer_time_unit(close_series.index)
    adx_series_name = f"{window_len}{time_str}ADX"
    adx_series = pd.Series(adx_array, index=close_series.index, name=adx_series_name)
    time_filtered_series = filter_dfs_by_time_range(
        df=adx_series, date_start=filter_date_start, date_end=filter_date_end
    )

    return time_filtered_series


import numpy as np


def get_available_chips_by_percent(
    price_centers: np.ndarray, daily_chip: np.ndarray, percent: float = 0.9
):
    """
    根据百分比保留中心筹码，去掉头尾两侧的筹码

    Args:
        price_centers: 长为 M 的升序价位数组
        daily_chip: 长为 M 的筹码数量或占比数组
        percent: 保留的中心筹码比例，默认 0.9 表示保留中间 90%

    Returns:
        (filtered_price_centers, filtered_daily_chip): 截取后的价位和筹码
    """
    # 1. 计算总筹码
    total_chip = np.sum(daily_chip)

    if total_chip == 0:
        # 如果总筹码为0，返回空数组
        return np.array([]), np.array([])

    # 2. 计算累计筹码占比
    cumsum = np.cumsum(daily_chip)
    cumsum_ratio = cumsum / total_chip

    # 3. 计算需要截断的比例
    # percent=0.9 表示去掉头 5% 和尾 5%
    left_ratio = (1 - percent) / 2  # 0.05
    right_ratio = (1 + percent) / 2  # 0.95

    # 4. 找到 left_ratio 和 right_ratio 对应的索引位置
    # 使用 np.searchsorted 找到插入位置
    left_idx = np.searchsorted(cumsum_ratio, left_ratio, side="left")
    right_idx = np.searchsorted(cumsum_ratio, right_ratio, side="right")

    # 5. 截取中间的价位和筹码
    filtered_price_centers = price_centers[left_idx : right_idx + 1]
    filtered_daily_chip = daily_chip[left_idx : right_idx + 1]

    return filtered_price_centers, filtered_daily_chip


def get_chips(
    volume_amount_series: pd.Series,
    market_cap_series: pd.Series,
    close_price_series: pd.Series,
    low_price_series: pd.Series,
    high_price_series: pd.Series,
    price_bins=100,
    filter_date_start: str = "",
    filter_date_end: str = "",
):
    """
    根据成交金额和价格区间估算每日筹码分布。

    Args:
        volume_amount_series (pd.Series): 每日成交金额序列。
        market_cap_series (pd.Series): 每日流通市值序列。
        close_price_series (pd.Series): 每日收盘价序列。
        low_price_series (pd.Series): 每日最低价序列。
        high_price_series (pd.Series): 每日最高价序列。
        price_bins (int, optional): 价格分箱数量，默认100。
        filter_date_start (str, optional): 目标数据起始时间。
        filter_date_end (str, optional): 目标数据终止时间。

    Returns:
        tuple: 收盘价索引、价格中心、筹码金额矩阵和归一化筹码矩阵。
    """
    time_filtered_series = filter_dfs_by_time_range(
        df=[
            volume_amount_series,
            market_cap_series,
            close_price_series,
            low_price_series,
            high_price_series,
        ],
        date_start=filter_date_start,
        date_end=filter_date_end,
    )
    volume_amount_series = time_filtered_series[0]
    market_cap_series = time_filtered_series[1]
    close_price_series = time_filtered_series[2]
    low_price_series = time_filtered_series[3]
    high_price_series = time_filtered_series[4]

    min_price = low_price_series.min() * 0.95
    max_price = high_price_series.max() * 1.05

    price_edges = np.linspace(min_price, max_price, price_bins + 1)
    price_centers = (price_edges[:-1] + price_edges[1:]) / 2
    n_days = len(close_price_series)

    daily_lows = low_price_series.values
    daily_highs = high_price_series.values
    daily_volume_amount = volume_amount_series.interpolate(
        method="linear", limit_direction="both"
    ).values
    daily_market_cap = market_cap_series.interpolate(
        method="linear", limit_direction="both"
    ).values

    # 金额尺度筹码时间序列初始化
    chip_matrix = np.zeros((n_days, price_bins), dtype=np.float32)
    chip_matrix_norm = np.zeros((n_days, price_bins), dtype=np.float32)

    # 存储每日新增筹码（按价格分布）
    daily_new_chips = np.zeros((n_days, price_bins), dtype=np.float32)

    # 得到大于该值所在序号的上一个序号，即左序号边缘
    low_indices = np.searchsorted(price_edges, daily_lows, side="right") - 1
    high_indices = np.searchsorted(price_edges, daily_highs, side="right") - 1
    # 流通市值均匀化假设
    chip_matrix[0, low_indices[0] : high_indices[0] + 1] = daily_market_cap[0] / (
        high_indices[0] - low_indices[0] + 1
    )
    daily_new_chips[0, low_indices[0] : high_indices[0] + 1] = daily_volume_amount[
        0
    ] / (high_indices[0] - low_indices[0] + 1)
    chip_matrix_norm[0, low_indices[0] : high_indices[0] + 1] = 1.0 / (
        high_indices[0] - low_indices[0] + 1
    )

    for i in range(1, n_days):
        l = low_indices[i]
        r = high_indices[i]
        n_covered = r - l + 1
        # 对上述序号区间范围，进行筹码金额分配，目前采用最简单的均匀分配
        daily_new_chips[i, l : r + 1] = daily_volume_amount[i] / n_covered
        turover_rate = daily_volume_amount[i] / daily_market_cap[i]
        # 求解昨日历史的筹码变化
        chip_matrix[i] = chip_matrix[i - 1] * (1 - turover_rate)
        # 累积今日变化的筹码
        chip_matrix[i, l : r + 1] += daily_new_chips[i, l : r + 1]
        # 调整缩放为和今日流通市值一致
        cur_sum = np.sum(chip_matrix[i])
        chip_matrix[i] *= daily_market_cap[i] / cur_sum
        chip_matrix_norm[i] = chip_matrix[i] / daily_market_cap[i]

    return (close_price_series.index, price_centers, chip_matrix, chip_matrix_norm)
