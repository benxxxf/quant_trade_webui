import pandas as pd
import zipfile
import re
import duckdb
import json

class CSMARParser:
    """
    CSMAR数据包解析器
    用来解析从从CSMAR上下载的ZIP数据包
    并根据需求转存CSV和写入DuckDB
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
            "行业编码"
        ]
        self.opt_time_list = [
            "统计截止日期",
            "交易日期",
            "统计日期",
            "交易月份",
            "变动日期",
            "月度标识"
        ]

    def parse_field_mapping(self, txt_content: str):
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

    def csmar_zip_to_df(self, zip_file: str) -> pd.DataFrame:
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
                    field_mapping, field_dict = self.parse_field_mapping(txt_content)
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
                            df = pd.read_csv(f, encoding="utf-8-sig",low_memory=False)
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

    def create_json_by_parquet_attrs(
        self, df: pd.DataFrame, meta_json_dir: str, parquet_file: str
    ):
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
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            print(f"✅ 元数据已保存到: {json_path}")
            return existing_data
        else:
            raise ValueError(f"Empty attrs in dataframe!")

    def save_df_to_parquet(
        self,
        df: pd.DataFrame,
        parquet_dir: str,
        parquet_name: str,
    ):
        id_pattern = "|".join(self.opt_id_list)
        id_matched_cols = df.columns[df.columns.str.contains(id_pattern, regex=True)]
        if len(id_matched_cols) > 0:
            ordered_id = id_matched_cols[0]
        else:
            raise ValueError(f"文件'{parquet_name}'中数据表ID未匹配到预选ID列表，当前列名为'{df.columns.tolist()}',请增添预选ID列表！")
        time_pattern = "|".join(self.opt_time_list)
        time_matched_cols = df.columns[
            df.columns.str.contains(time_pattern, regex=True)
        ]
        if len(time_matched_cols) > 0:
            ordered_time = time_matched_cols[0]
        else:
            raise ValueError(f"文件'{parquet_name}'中数据表时间未匹配预选时间列表，当前列名为'{df.columns.tolist()}',请增添预选时间列表！")
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
        is_numeric = df[ordered_id].str.match(r'^\d+$', na=False)
    
    # 纯数字：转为 int 去掉前导零，再转回字符串
        df.loc[is_numeric, ordered_id] = df.loc[is_numeric, ordered_id].astype(int).astype(str)
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

    def update_to_database(
        self, csmar_zips_dir: str, database_parquets_dir: str, target_zip_files=[]
    ):
        """_summary_

        Args:
            csmar_zips_dir (str): 从CSMAR下载的ZIP文件夹目录
            database_parquets_dir (str): 输出PARQUET数据库文件的文件夹目录
            target_zip_files (list): 待处理的ZIP文件清单，如果为空则处理ZIP文件夹下所有ZIP
        """
        pattern = re.compile(r"^(.*?)\d+.*\.zip$", re.IGNORECASE)
        zip_files_info = []
        csmar_zips_folder_path = Path(csmar_zips_dir)

        file_path_list = []
        if not target_zip_files:
            for file_path in csmar_zips_folder_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == ".zip":
                    file_path_list.append(file_path)
        else:
            for file_path_str in target_zip_files:
                file_path = Path(file_path_str)
                if file_path.is_file() and file_path.suffix.lower() == ".zip":
                    file_path_list.append(file_path)

        for file_path in file_path_list:
            # 检查是否为文件且后缀为.zip（不区分大小写）
            # if file_path.is_file() and file_path.suffix.lower() == ".zip":
            # 获取完整文件名
            file_name_full = file_path.name

            # 使用正则提取"XXX"部分
            match = pattern.match(file_name_full)
            if match:
                file_name = match.group(1)  # 提取的"XXX"部分
                cur_dict = {
                    "file_path": [str(file_path)],
                    "file_name": file_name,
                }
                has_same_file_name = False
                for it in zip_files_info:
                    if cur_dict["file_name"] == it["file_name"]:
                        it["file_path"].append(str(file_path))
                        has_same_file_name = True
                        break
                if has_same_file_name == False:
                    zip_files_info.append(cur_dict)
            else:
                # 如果文件名格式不匹配，可以选择跳过或记录警告
                print(f"跳过不匹配的文件: {file_name_full}")
        # 两个循环不合并，方便维护调试
        # csmar_parser = CSMARParser()
        for it in zip_files_info:
            if len(it["file_path"]) == 1:
                it_df = self.csmar_zip_to_df(it["file_path"][0])
                self.save_df_to_parquet(
                    df=it_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            elif len(it["file_path"]) > 1:
                all_dfs = []
                for it_file in it["file_path"]:
                    cur_it_df = self.csmar_zip_to_df(it_file)
                    all_dfs.append(cur_it_df)
                combined_df = pd.concat(all_dfs, ignore_index=True)
                combined_df.attrs = all_dfs[0].attrs
                self.save_df_to_parquet(
                    df=combined_df,
                    parquet_dir=database_parquets_dir,
                    parquet_name=it["file_name"],
                )
            else:
                raise ValueError(f"{it["file_name"]}中包含的实际文件数量为0！")
        return zip_files_info

    def get_file_cols_by_meta_json(self, database_dir: str):
        """_summary_

        Args:
            database_dir (str): 数据库文件夹路径

        Raises:
            ValueError: 数据库下不存在meta.json描述文件

        Returns:
            _type_: 每个数据库文件包含的中文列名
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
        # 获取每个数据库文件和中文列名的映射字典
        file_cols = self.get_file_cols_by_meta_json(database_dir=database_dir)
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
            """在DataFrame中查找第一个匹配的列名"""
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
            df_it.sort_values(["代码", "时间"], ascending=[True, True], inplace=True)

        # 根据ID和Time，重新合并表格并输出
        merged_df = df_list[0]
        for df_it in df_list[1:]:
            merged_df = pd.merge(merged_df, df_it, on=["代码", "时间"], how="outer")
        merged_df.sort_values(["代码", "时间"], ascending=[True, True], inplace=True)

        print("✅️完成指定列名数据表构建。")
        return merged_df, df_list

    def fillna_by_id_group(
        self,
        df: pd.DataFrame,
        grouped_id_str="代码",
        use_forward_fill: bool = True,
        spec_col_names: list = [],
    ):
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