from quant_trade_webui_deps.database_parser import *
from quant_trade_webui_deps.dataframe_plotter import *


class DataframePlotterExample1(DataFramePlotter):
    """
    从Parquet数据库中加载并查看深证成指的数据脚本
    """

    def __init__(self):
        exe_dir_path = Path(sys.argv[0]).resolve().parent.as_posix()
        local_parser = DatabaseParser()
        merged_df, df_list = local_parser.create_df_from_database(
            data_col_list=[
                "开盘指数",
                "最高指数",
                "最低指数",
                "收盘指数",
                "成份证券成交量",
                "成份证券成交金额",
                "样本股组合流通市值",
            ],
            database_dir=f"{exe_dir_path}/example_database",
            data_preferfile_dict={
                "开盘指数": f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet",
                "最高指数": f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet",
                "最低指数": f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet",
                "收盘指数": f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet",
                "成份证券成交量": f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet",
                "成份证券成交金额": f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet",
            },
            file_sql_appendcmd={
                f"{exe_dir_path}/example_database/国内指数日行情文件_19901219_20260729.parquet": "WHERE 交易所指数代码='399001'",
                f"{exe_dir_path}/example_database/国内股票指数日市值文件_19910715_20260729.parquet": "WHERE 交易所指数代码='399001'",
            },
        )
        merged_df["成份证券成交量"] = merged_df["成份证券成交量"] * 10000
        merged_df["成份证券成交金额"] = merged_df["成份证券成交金额"] * 10000
        merged_df["样本股组合流通市值"] = merged_df["样本股组合流通市值"] * 1000
        merged_df["收益率"] = merged_df["收盘指数"].pct_change()

        time_start = "20100101"
        time_end = ""
        super().__init__(
            name="深证成指",
            df=merged_df,
            open_col="开盘指数",
            high_col="最高指数",
            low_col="最低指数",
            close_col="收盘指数",
            time_start=time_start,
            time_end=time_end,
        )
        self.create_fig()
        print(f"{self.name}数据加载器构建完成")

    def create_fig(self):
        close_sma_20 = get_window_value(
            series=self.df[self.close_col],
            window_len=20,
            method_type=WindowMethodType.AVG_METHOD,
            weight_allocation=WeightAllocationType.SMA,
            filter_date_start=self.time_start_str,
            filter_date_end=self.time_end_str,
        )
        close_sma_5 = get_window_value(
            series=self.df[self.close_col],
            window_len=5,
            method_type=WindowMethodType.AVG_METHOD,
            weight_allocation=WeightAllocationType.SMA,
            filter_date_start=self.time_start_str,
            filter_date_end=self.time_end_str,
        )
        volume_amount_sma_20 = get_window_value(
            series=self.df["成份证券成交金额"],
            window_len=20,
            method_type=WindowMethodType.AVG_METHOD,
            weight_allocation=WeightAllocationType.SMA,
            filter_date_start=self.time_start_str,
            filter_date_end=self.time_end_str,
        )
        volume_amount_sma_5 = get_window_value(
            series=self.df["成份证券成交金额"],
            window_len=5,
            method_type=WindowMethodType.AVG_METHOD,
            weight_allocation=WeightAllocationType.SMA,
            filter_date_start=self.time_start_str,
            filter_date_end=self.time_end_str,
        )

        self.add_line_to_plot(close_sma_20, y_axis="y")
        self.add_line_to_plot(close_sma_5, y_axis="y")
        self.add_line_to_plot(volume_amount_sma_20, y_axis="y2")
        self.add_line_to_plot(volume_amount_sma_5, y_axis="y2")
        time_filtered_volume_amount_series = filter_dfs_by_time_range(
            self.df["成份证券成交金额"], self.time_start_str, self.time_end_str
        )
        self.update_series_to_ranged_df(time_filtered_volume_amount_series)
        return_rate_series = get_return_rate(
            self.df["收盘指数"], 1, self.time_start_str, self.time_end_str
        )
        volume_amount_color_list = [
            self.pos_color if val > 0 else self.neg_color
            for val in return_rate_series
        ]
        self.add_bar_to_plot(
            time_filtered_volume_amount_series,
            y_axis="y2",
            colors_list=volume_amount_color_list,
        )
        
        return self.fig
