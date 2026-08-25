from .common_utils import *
from collections import defaultdict
import zipfile
import re
import duckdb


class DatabaseParser:
    """
    Database数据包解析器
    封装了本地数据库相关操作
    """

    def __init__(self):
        """
        初始化时传入配置，一次配置多次使用
        """
        self.opt_id_list = [
            "证券代码",
            "股票代码",
            "市场类型",
            "股票市场类型编码",
            "无风险利率基准",
            "指数代码",
            "综合市场类型",
            "合约简称",
            "交易所指数代码",
            "行业编码",
            "频率标识",
        ]
        self.opt_time_list = [
            "统计截止日期",
            "交易日期",
            "统计日期",
            "交易月份",
            "变动日期",
            "月度标识",
        ]

    def _parse_field_mapping(self, txt_content: str):
        """
        解析TXT文件中的字段映射关系
        格式: Stkcd [证券代码] - 以沪深京交易所公布的证券代码为准。
        返回: {'Stkcd': '证券代码', 'Disttyp': '分配类型', ...}
        """
        txt_mapping = {}
        txt_dict = {}

        # 按行分割
        lines = txt_content.strip().split("\n")
        ind = 1

        for line in lines:
            # 匹配格式: 英文名 [中文名]
            # 使用正则提取
            pattern = re.compile(r"^([^\s]+)\s*\[([^\]]+)\]\s*-\s*(.+)$")
            match = pattern.match(line)
            if match:
                english_name = match.group(1)
                chinese_name = match.group(2)
                annotation = match.group(3).rstrip("\r")
                txt_dict[f"col{ind}"] = {
                    "english_name": english_name,
                    "chinese_name": chinese_name,
                    "annotation": annotation,
                }
                ind += 1
                txt_mapping[english_name] = chinese_name

        return txt_mapping, txt_dict

    def _csmar_zip_to_df(self, zip_file: str) -> pd.DataFrame:
        """
        读取CSMAR ZIP数据包并合并为DataFrame。

        ZIP包中的CSV、JSON或Excel文件会被读取；如果存在TXT字段说明文件，
        则根据其中的映射关系将英文列名转换为中文列名，并将字段元数据保存到
        返回DataFrame的attrs属性中。

        Args:
            zip_file: CSMAR ZIP数据包路径。

        Returns:
            合并后的DataFrame；当ZIP包中没有可读取的数据文件时返回空DataFrame。
        """
        all_dfs = []
        with zipfile.ZipFile(zip_file, "r") as z:
            # 先看看里面有什么
            print("ZIP里的文件列表:", z.namelist())
            data_files = [
                f
                for f in z.namelist()
                if f.endswith((".csv", ".json", ".xlsx", ".xls"))
            ]
            txt_files = [f for f in z.namelist() if f.endswith(".txt")]
            if txt_files:
                txt_file = txt_files[0]  # 取第一个TXT文件
                with z.open(txt_file) as f:
                    txt_content = f.read().decode("utf-8-sig", errors="ignore")
                    field_mapping, field_dict = self._parse_field_mapping(txt_content)
                print(f"找到字段映射文件: {txt_file}")
                print(f"映射关系: {len(field_mapping)} 个字段")
            else:
                print("警告: 未找到TXT映射文件，将使用原始列名")

            if not data_files:
                print(f"警告: {zip_file} 中没有找到数据文件")
                return pd.DataFrame()

            print(f"找到 {len(data_files)} 个数据文件:")
            for data_file in data_files:
                print(f"  - {data_file}")
                try:
                    with z.open(data_file) as f:
                        if data_file.endswith(".csv"):
                            df = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
                        elif data_file.endswith(".json"):
                            df = pd.read_json(f, lines=True)
                        elif data_file.endswith((".xlsx", ".xls")):
                            df = pd.read_excel(f)
                        else:
                            raise ValueError(f"不支持的文件格式: {data_file}")
                        # 3. 应用字段映射（只替换存在的列）
                        if field_mapping:
                            # 只映射在field_mapping中存在的列
                            rename_dict = {
                                col: field_mapping[col]
                                for col in df.columns
                                if col in field_mapping
                            }
                            df = df.rename(columns=rename_dict)
                            print(f"    已替换 {len(rename_dict)} 个列名")

                        all_dfs.append(df)
                except Exception as e:
                    print(f"  读取 {data_file} 失败: {e}")
                    continue

            # 合并所有DataFrame
            if all_dfs:
                combined_df = pd.concat(all_dfs, ignore_index=True)
                combined_df.attrs = field_dict
                print(f"合并完成，共 {len(combined_df)} 行数据")
                return combined_df
            else:
                return pd.DataFrame()

    def _df_info_to_dict(self, df: pd.DataFrame):
        txt_dict = {}
        ind = 1
        for col_name in df.columns:
            txt_dict[f"col{ind}"] = {
                "english_name": "",
                "chinese_name": col_name,
                "annotation": "",
            }
            ind += 1
        return txt_dict

    def _csv_to_df(self, file_path, **kwargs):
        """
        将CSV文件转换为DataFrame，自动识别编码

        Args:
            file_path: CSV文件路径

        Returns:
            DataFrame
        """
        # 常见编码列表（按优先级排序）
        encodings = [
            "utf-8-sig",  # 带BOM的UTF-8（Excel保存的UTF-8）
            "utf-8",  # 标准UTF-8
            "gb18030",  # 中文全集（包含GBK/GB2312）
            "gbk",  # Windows中文默认
            "gb2312",  # 简体中文
            "big5",  # 繁体中文
            "latin-1",  # 兜底编码（不会报错，但可能乱码）
        ]

        # 尝试每个编码
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding, **kwargs)
                # 简单验证：检查是否有不可读字符（可选）
                # 如果包含大量乱码特征，可以继续尝试下一个编码
                df.attrs = self._df_info_to_dict(df)
                return df
            except UnicodeDecodeError:
                continue
            except Exception:
                # 其他错误（如文件不存在）直接抛出
                raise

        # 所有编码都失败
        raise ValueError(f"无法读取CSV文件: {file_path}")

    def _parquet_to_df(self, file_path, **kwargs):
        df = pd.read_parquet(file_path, **kwargs)
        df.attrs = self._df_info_to_dict(df)
        return df

    def create_json_by_parquet_attrs(
        self, df: pd.DataFrame, meta_json_dir: str, parquet_file: str
    ):
        """
        根据DataFrame元数据创建或更新Parquet文件索引。

        函数读取目标目录中的meta.json，比较指定Parquet文件已有的字段元数据，
        并在元数据发生变化或首次出现时写回索引文件。

        Args:
            df: 包含字段元数据的DataFrame，元数据存放在attrs属性中。
            meta_json_dir: meta.json所在目录。
            parquet_file: 需要登记元数据的Parquet文件路径。

        Returns:
            更新后的元数据字典。

        Raises:
            ValueError: DataFrame未包含元数据时抛出。
        """
        if df.attrs:
            meta_json_dir_path = Path(meta_json_dir)
            meta_json_dir_path.mkdir(parents=True, exist_ok=True)
            json_path = meta_json_dir_path / "meta.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
            else:
                existing_data = {}
            # 5. 检查是否需要更新
            if parquet_file in existing_data:
                # 比较现有数据和新的attrs是否一致
                if existing_data[parquet_file] == df.attrs:
                    print(f"⏭️  跳过: {parquet_file} 的元数据已存在且一致")
                    return existing_data
                else:
                    print(f"🔄 更新: {parquet_file} 的元数据发生了变化")
            else:
                print(f"➕ 新增: {parquet_file}")

            # 6. 更新或添加新数据
            existing_data[parquet_file] = df.attrs

            # 7. 写回JSON文件（格式化输出，方便阅读）
            self._overwrite_meta_json(meta_json_dir, existing_data)
            return existing_data
        else:
            raise ValueError(f"空参数Dataframe!")

    def _save_df_to_parquet(
        self,
        df: pd.DataFrame,
        parquet_dir: str,
        parquet_name: str,
    ):
        """
        将DataFrame按证券代码和时间排序后保存为Parquet文件。

        函数会自动识别代码列和时间列，规范化代码格式，根据数据日期生成文件名，
        并通过DuckDB执行新建或去重增量追加操作。

        Args:
            df: 待保存的数据表。
            parquet_dir: Parquet数据库目录。
            parquet_name: Parquet文件的基础名称。

        Raises:
            ValueError: 未识别到证券代码列或时间列时抛出。
        """
        id_pattern = "|".join(self.opt_id_list)
        id_matched_cols = df.columns[df.columns.str.contains(id_pattern, regex=True)]
        if len(id_matched_cols) > 0:
            ordered_id = id_matched_cols[0]
        else:
            raise ValueError(
                f"文件'{parquet_name}'中数据表ID未匹配到预选ID列表，当前列名为'{df.columns.tolist()}',请增添预选ID列表！"
            )
        time_pattern = "|".join(self.opt_time_list)
        time_matched_cols = df.columns[
            df.columns.str.contains(time_pattern, regex=True)
        ]
        if len(time_matched_cols) > 0:
            ordered_time = time_matched_cols[0]
        else:
            raise ValueError(
                f"文件'{parquet_name}'中数据表时间未匹配预选时间列表，当前列名为'{df.columns.tolist()}',请增添预选时间列表！"
            )
        Path(parquet_dir).mkdir(parents=True, exist_ok=True)
        df[ordered_time] = pd.to_datetime(df[ordered_time])
        oldest_date = df[ordered_time].min()
        newest_date = df[ordered_time].max()
        oldest_date_str = oldest_date.strftime("%Y%m%d")
        newest_date_str = newest_date.strftime("%Y%m%d")
        parquet_file = (
            f"{parquet_dir}/{parquet_name}_{oldest_date_str}_{newest_date_str}.parquet"
        )
        self.create_json_by_parquet_attrs(
            df=df, meta_json_dir=parquet_dir, parquet_file=parquet_file
        )
        df[ordered_id] = df[ordered_id].astype(str).str.strip()

        # 判断是否为纯数字（正则匹配：只包含0-9）
        is_numeric = df[ordered_id].str.match(r"^\d+$", na=False)

        # 纯数字：转为 int 去掉前导零，再转回字符串
        df.loc[is_numeric, ordered_id] = (
            df.loc[is_numeric, ordered_id].astype(int).astype(str)
        )
        # 设置高性能参数
        duckdb.sql("SET memory_limit = '32GB'")  # 根据内存调整
        duckdb.sql("SET threads = 12")  # 根据CPU核数调整
        if not os.path.exists(parquet_file):
            # 2. 文件不存在，直接创建新表（写入全部数据）
            print(f"📦 Parquet 文件不存在，正在创建: {parquet_file}")
            duckdb.sql(f"""
                COPY (
                    SELECT * FROM df
                    ORDER BY {ordered_id}, {ordered_time}
                ) TO '{parquet_file}' (
                    FORMAT PARQUET,
                    COMPRESSION 'zstd',
                    COMPRESSION_LEVEL 9,  -- 最高压缩比
                    ROW_GROUP_SIZE 100000  -- 平衡查询和压缩
                )
            """)
            print(f"✅ 文件创建完成，在{parquet_file}中新增了 {len(df)} 条新数据")
        else:
            # 3. 文件存在，执行去重增量追加
            print(f"📝 文件已存在，执行增量追加...")
            duckdb.sql(
                f"CREATE OR REPLACE TABLE temp_parquet AS SELECT * FROM read_parquet('{parquet_file}')"
            )
            old_count = duckdb.sql("SELECT COUNT(*) FROM temp_parquet").fetchone()[0]
            duckdb.sql(f"""
                INSERT INTO temp_parquet
                SELECT d.* 
                FROM df d
                LEFT JOIN temp_parquet p
                    ON d.{ordered_id} = p.{ordered_id} 
                    AND d.{ordered_time} = p.{ordered_time}
                WHERE p.{ordered_id} IS NULL
            """)
            new_count = duckdb.sql("SELECT COUNT(*) FROM temp_parquet").fetchone()[0]
            inserted_count = new_count - old_count

            if inserted_count > 0:
                duckdb.sql(f"""
                    COPY (
                        SELECT * FROM temp_parquet
                        ORDER BY {ordered_id}, {ordered_time}
                    ) TO '{parquet_file}' (
                        FORMAT PARQUET,
                        COMPRESSION 'zstd',
                        COMPRESSION_LEVEL 9,
                        ROW_GROUP_SIZE 100000
                    )
                """)
                print(
                    f"✅ 文件追加完成，{parquet_file}已有{old_count}数据，新增 {inserted_count} 条数据"
                )
            else:
                print("⏭️ 无新数据，Parquet 文件未更新")

    def _check_meta_json(self, database_parquets_dir: str):
        """
        读取Parquet数据库目录中的元数据索引文件。

        Args:
            database_parquets_dir: Parquet数据库目录。

        Returns:
            meta.json中的元数据字典。

        Raises:
            ValueError: 目录下不存在meta.json时抛出。
        """
        meta_json_path = os.path.join(database_parquets_dir, "meta.json")
        if os.path.exists(meta_json_path):
            with open(meta_json_path, "r", encoding="utf-8") as f:
                meta_data = json.load(f)
        else:
            raise ValueError(
                f"路径'{database_parquets_dir}'下不存在meta.json文件,请确认是否为标准数据库！"
            )
        return meta_data

    def _overwrite_meta_json(self, database_parquets_dir: str, meta_data={}):
        """
        将元数据字典覆盖写入数据库目录下的meta.json。

        Args:
            database_parquets_dir: Parquet数据库目录。
            meta_data: 需要写入的元数据字典，默认为空字典。
        """
        meta_json_path = os.path.join(database_parquets_dir, "meta.json")
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=4)

    def _check_parquets_exist(self, database_parquets_dir: str):
        """
        检查元数据索引中的Parquet文件是否仍然存在。

        对于已经从磁盘删除的文件，调用删除方法清理meta.json中的对应记录。

        Args:
            database_parquets_dir: Parquet数据库目录。
        """
        meta_data = self._check_meta_json(database_parquets_dir)

        # cleaned_meta_data=copy.deepcopy(meta_data)
        ready_clean_parquets = []
        for file_name, file_info in meta_data.items():
            if not os.path.exists(file_name):
                print(f"文件'{file_name}'不存在,将从meta.json中清理元数据信息。")
                ready_clean_parquets.append(file_name)
                # del cleaned_meta_data[file_name]
        self.delet_from_database(database_parquets_dir, ready_clean_parquets)
        print(f"✅️完成对'{ready_clean_parquets}'失效数据包清理。")

    def delet_from_database(self, database_parquets_dir: str, target_parquets_files):
        """
        删除指定的Parquet文件并同步清理元数据索引。

        Args:
            database_parquets_dir: 待操作的Parquet数据库目录。
            target_parquets_files: 待删除的Parquet文件路径列表。
        """
        meta_data = self._check_meta_json(database_parquets_dir)
        cleaned_meta_data = copy.deepcopy(meta_data)
        for parquet_file in target_parquets_files:
            if parquet_file in meta_data:
                del cleaned_meta_data[parquet_file]
            else:
                print(f"待删除文件{parquet_file}未登录在数据库中。")
            if os.path.exists(parquet_file):
                os.remove(parquet_file)
                print(f"数据库成功删除{parquet_file}文件。")
            else:
                print(f"待删除文件{parquet_file}不存在，无需删除。")
        self._overwrite_meta_json(database_parquets_dir, cleaned_meta_data)

    def _merge_files_by_pattern(self, file_path_list: list, pattern):
        merged_files_info = []
        for file_path in file_path_list:
            # 获取完整文件名
            file_name_full = file_path.name
            # 使用正则提取"XXX"部分
            match = re.search(pattern, file_name_full)
            if match:
                file_name = match.group(1)  # 提取的"XXX"部分
                cur_dict = {
                    "file_path": [str(file_path)],
                    "file_name": file_name,
                }
                has_same_file_name = False
                for it in merged_files_info:
                    if cur_dict["file_name"] == it["file_name"]:
                        it["file_path"].append(str(file_path))
                        has_same_file_name = True
                        break
                if has_same_file_name == False:
                    merged_files_info.append(cur_dict)
            else:
                # 如果文件名格式不匹配，可以选择跳过或记录警告
                print(f"跳过不匹配的文件: {file_name_full}")
        return merged_files_info

    def update_to_database_by_csmar_zips(
        self, database_parquets_dir: str, target_zip_files: list
    ):
        """
        批量解析CSMAR ZIP文件并更新Parquet数据库。

        函数按文件名归并同一数据表的多个ZIP包，解析后合并数据，并通过增量去重
        的方式写入数据库。

        Args:
            csmar_zips_dir: 从CSMAR下载的ZIP文件夹目录。
            database_parquets_dir: 输出Parquet数据库文件的目录。
            target_zip_files: 待处理的ZIP文件路径列表；为空时处理目录下所有ZIP文件。

        Returns:
            按数据表名称归并后的ZIP文件信息列表。
        """
        pattern = r"^(.*?)\d+\([^)]*\)\.[^.]+$"

        file_path_list = []
        for file_path_str in target_zip_files:
            file_path = Path(file_path_str)
            if file_path.is_file() and file_path.suffix.lower() == ".zip":
                file_path_list.append(file_path)

        zip_files_info = self._merge_files_by_pattern(file_path_list, pattern)

        for it in zip_files_info:
            if len(it["file_path"]) == 1:
                it_df = self._csmar_zip_to_df(it["file_path"][0])
                self._save_df_to_parquet(
                    df=it_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            elif len(it["file_path"]) > 1:
                all_dfs = []
                for it_file in it["file_path"]:
                    cur_it_df = self._csmar_zip_to_df(it_file)
                    all_dfs.append(cur_it_df)
                combined_df = pd.concat(all_dfs, ignore_index=True)
                combined_df.attrs = all_dfs[0].attrs
                self._save_df_to_parquet(
                    df=combined_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            else:
                raise ValueError(f"{it["file_name"]}中包含的实际文件数量为0！")
        return zip_files_info

    def update_to_database_by_csvs(
        self, database_parquets_dir: str, target_csv_files: list
    ):
        pattern = r"^([^\s_\-\(\)\[\]\{\}]+)"
        file_path_list = []
        for file_path_str in target_csv_files:
            file_path = Path(file_path_str)
            if file_path.is_file() and file_path.suffix.lower() == ".csv":
                file_path_list.append(file_path)
        csv_files_info = self._merge_files_by_pattern(file_path_list, pattern)

        for it in csv_files_info:
            if len(it["file_path"]) == 1:
                it_df = self._csv_to_df(it["file_path"][0])
                self._save_df_to_parquet(
                    df=it_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            elif len(it["file_path"]) > 1:
                all_dfs = []
                for it_file in it["file_path"]:
                    cur_it_df = self._csv_to_df(it_file)
                    all_dfs.append(cur_it_df)
                combined_df = pd.concat(all_dfs, ignore_index=True)
                combined_df.attrs = all_dfs[0].attrs
                self._save_df_to_parquet(
                    df=combined_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            else:
                raise ValueError(f"{it["file_name"]}中包含的实际文件数量为0！")
        return csv_files_info

    def update_to_database_by_parquets(
        self, database_parquets_dir: str, target_parquet_files: list
    ):
        pattern = r"^([^\s_\-\(\)\[\]\{\}]+)"
        file_path_list = []
        for file_path_str in target_parquet_files:
            file_path = Path(file_path_str)
            if file_path.is_file() and file_path.suffix.lower() == ".parquet":
                file_path_list.append(file_path)
        parquet_files_info = self._merge_files_by_pattern(file_path_list, pattern)

        for it in parquet_files_info:
            if len(it["file_path"]) == 1:
                it_df = self._parquet_to_df(it["file_path"][0])
                self._save_df_to_parquet(
                    df=it_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            elif len(it["file_path"]) > 1:
                all_dfs = []
                for it_file in it["file_path"]:
                    cur_it_df = self._parquet_to_df(it_file)
                    all_dfs.append(cur_it_df)
                combined_df = pd.concat(all_dfs, ignore_index=True)
                combined_df.attrs = all_dfs[0].attrs
                self._save_df_to_parquet(
                    df=combined_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            else:
                raise ValueError(f"{it["file_name"]}中包含的实际文件数量为0！")
        return parquet_files_info

    def update_to_database_by_dir(self, database_parquets_dir: str, target_dir: str):
        zip_files = []
        csv_files = []
        parquet_files = []
        csmar_zips_folder_path = Path(target_dir)
        for file_path in csmar_zips_folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() == ".zip":
                zip_files.append(file_path)
            elif file_path.is_file() and file_path.suffix.lower() == ".csv":
                csv_files.append(file_path)
            elif file_path.is_file() and file_path.suffix.lower() == ".parquet":
                parquet_files.append(file_path)
        if zip_files:
            self.update_to_database_by_csmar_zips(database_parquets_dir, zip_files)
        if csv_files:
            self.update_to_database_by_csvs(database_parquets_dir, csv_files)
        if parquet_files:
            self.update_to_database_by_parquets(database_parquets_dir, parquet_files)

    def _get_file_cols_by_meta_json(self, database_dir: str):
        """
        从meta.json中读取每个数据库文件包含的中文列名。

        Args:
            database_dir: 数据库文件夹路径。

        Raises:
            ValueError: 数据库下不存在meta.json描述文件。

        Returns:
            每个数据库文件及其中文列名列表组成的字典。
        """
        json_path = Path(f"{database_dir}/meta.json")
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                file_cols = {}
                for file_name_key, dict_info_val in json_data.items():
                    file_cols[file_name_key] = []
                    for col_ind_key, col_info_val in dict_info_val.items():
                        file_cols[file_name_key].append(col_info_val["chinese_name"])
        else:
            raise ValueError(f"数据库信息索引文件meta.json在{database_dir}下不存在！")
        return file_cols

    def create_df_from_database(
        self,
        data_col_list: list[str],
        database_dir: str,
        data_preferfile_dict: dict = {},
        file_sql_appendcmd: dict = {},
    ):
        """
        从Parquet数据库中按需求列构建合并后的DataFrame。

        函数根据meta.json定位需求列所在的文件，可使用指定的倾向文件和SQL追加条件，
        读取各文件后统一代码、时间列名称，并按代码和时间外连接合并数据。

        Args:
            data_col_list: 需要查询的中文列名列表。
            database_dir: Parquet数据库目录。
            data_preferfile_dict: 列名到倾向查询文件的映射字典。
            file_sql_appendcmd: 文件路径到SQL追加条件的映射字典。

        Returns:
            合并后的DataFrame，以及按来源文件读取的DataFrame列表。
        """
        # 获取每个数据库文件和中文列名的映射字典
        file_cols = self._get_file_cols_by_meta_json(database_dir=database_dir)
        # 根据数据库文件和中文列名的映射字典，得到用户需求列名与数据库文件的映射字典
        usercol_file_dict = {}
        for it_col in data_col_list:
            find_flag = False
            if it_col in data_preferfile_dict:
                if it_col in file_cols[data_preferfile_dict[it_col]]:
                    print(
                        f"用户倾向文件'{data_preferfile_dict[it_col]}'中成功匹配列名'{it_col}'."
                    )
                    usercol_file_dict[it_col] = data_preferfile_dict[it_col]
                    find_flag = True
                else:
                    print(
                        f"用户倾向文件'{data_preferfile_dict[it_col]}'中未能成功匹配列名'{it_col}'，回退自动匹配模式."
                    )
                    find_flag = False
            if find_flag is False:
                for file_name, cols_list in file_cols.items():
                    if it_col in cols_list:
                        print(
                            f"成功在'{file_name}'数据库文件中匹配用户定义列名'{it_col}'."
                        )
                        usercol_file_dict[it_col] = file_name
                        find_flag = True
                        break
            if find_flag is False:
                print(f"用户定义列名'{it_col}'未能匹配数据库中列名，请确认列名正确性！")
        # 根据用户需求列名与数据库文件的映射字典，得到数据库文件和用户需求列名的反向映射，注意用户需求列名是list类型
        file_usercol_dict = defaultdict(list)
        for key, value in usercol_file_dict.items():
            file_usercol_dict[value].append(key)
        file_usercol_dict = dict(file_usercol_dict)
        df_list = []
        # 根据上述结构，用duckdb从各个数据库文件中，根据需求列名分别读取各表，组合成dataframe的list结构
        for file, usercol in file_usercol_dict.items():
            select_parts = []
            for id_col in self.opt_id_list:
                if id_col in file_cols[file]:
                    select_parts.append(id_col)
                    break
            for time_col in self.opt_time_list:
                if time_col in file_cols[file]:
                    select_parts.append(time_col)
                    break
            select_parts += usercol
            quoted_parts = [f'"{col}"' for col in select_parts]
            if file in file_sql_appendcmd:
                query = f"SELECT {', '.join(quoted_parts)} FROM '{file}' {file_sql_appendcmd[file]}"
            else:
                query = f"SELECT {', '.join(quoted_parts)} FROM '{file}'"
            df_list.append(duckdb.sql(query).df())

        # 将各个dataframe中表示证券代码和参考时间的列名重新统一命名
        def find_column(df: pd.DataFrame, options):
            """
            在DataFrame中查找候选列名中的第一个匹配项。

            Args:
                df: 待查找的DataFrame。
                options: 候选列名列表。

            Returns:
                在DataFrame中找到的第一个候选列名。

            Raises:
                ValueError: 没有任何候选列名存在于DataFrame中时抛出。
            """
            for col in options:
                if col in df.columns:
                    return col
            raise ValueError(f"在DataFrame中找不到以下列名: {options}")

        for df_it in df_list:
            cur_id_col = find_column(df_it, self.opt_id_list)
            cur_time_col = find_column(df_it, self.opt_time_list)
            df_it.rename(
                columns={cur_id_col: "代码", cur_time_col: "时间"}, inplace=True
            )
            df_it.set_index("时间", inplace=True)
            df_it.sort_values(["代码"], ascending=[True], inplace=True)

        # 根据ID和Time，重新合并表格并输出
        merged_df = df_list[0]
        for df_it in df_list[1:]:
            merged_df = pd.merge(merged_df, df_it, on=["代码", "时间"], how="outer")
        # merged_df.set_index("时间", inplace=True)
        merged_df.sort_values(["代码"], ascending=[True], inplace=True)

        print("✅️完成指定列名数据表构建。")
        return merged_df, df_list

    def fillna_by_id_group(
        self,
        df: pd.DataFrame,
        grouped_id_str="代码",
        use_forward_fill: bool = True,
        spec_col_names: list = [],
    ):
        """
        按证券代码分组，对指定列执行前向或后向缺失值填充。

        Args:
            df: 待处理的DataFrame。
            grouped_id_str: 用于分组的证券代码列名，默认为“代码”。
            use_forward_fill: 是否使用前向填充；为False时使用后向填充。
            spec_col_names: 需要填充的指定列名列表；为空时填充所有列。

        Returns:
            完成分组缺失值填充后的DataFrame。
        """
        if spec_col_names:
            fill_cols = [col for col in df.columns if col in spec_col_names]
        else:
            fill_cols = df.columns
        df_filled = (
            df.groupby(grouped_id_str)[fill_cols].ffill()
            if use_forward_fill
            else df.groupby(grouped_id_str)[fill_cols].bfill()
        )
        return df_filled
