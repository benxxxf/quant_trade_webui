from .custom_control import *
from .database_parser import *
import streamlit as st
import pandas as pd


def database_manager_qtw_page():
    """
    用于将各种类型数据包，融合为本地PARQUET格式数据库功能页
    从而降低内存占用提升访问速度
    """

    if "meta_data" not in st.session_state:
        st.session_state.meta_data = None
    if "show_expander" not in st.session_state:
        st.session_state.show_expander = False

    local_parser = DatabaseParser()

    # 选择本地数据库文件夹路径
    with st.sidebar:
        st.header("数据库路径选择")
        db_dir = folder_browser("db_dir_selector")
    if not db_dir or not os.path.isdir(db_dir):
        st.write(f"⬅️ 请选择有效的数据库文件夹")
        st.stop()

        # 本地数据库下会有个meta.json文件管理所有数据包，如果没有的话可以用"新增"按钮逐个包构建
    meta_json_path = os.path.join(db_dir, "meta.json")

    with st.sidebar:
        # 同步一下meta.json登记的所有数据包信息
        if st.button("🔄 同步", width="stretch"):
            if os.path.exists(meta_json_path):
                with open(meta_json_path, "r", encoding="utf-8") as f:
                    st.session_state.meta_data = json.load(f)
                    st.success("✅ 解析成功！")
            else:
                st.info(f"❌ 数据库{db_dir}下找不到 meta.json 文件，将会设定为新数据库")
            st.header("数据库更新")

        # 选择更新数据库方式，目前仅支持存放CSMAR下载的ZIP文件，其文件夹批量更新和单个ZIP更新
        update_mode = st.selectbox(
            label="更新数据库",
            options=[
                "文件夹批量更新",
                "指定ZIP文件更新",
                "指定CSV文件更新",
                "指定PARQUET文件更新",
            ],
            label_visibility="collapsed",
        )
        if update_mode == "文件夹批量更新":
            folder_browser("rawdata_dir_selector")
        elif update_mode == "指定ZIP文件更新":
            files_browser("zip_files_selector", file_types=[("压缩文件", "*.zip")])
        elif update_mode == "指定CSV文件更新":
            files_browser("csv_files_selector", file_types=[("CSV文件", "*.csv")])
        elif update_mode == "指定PARQUET文件更新":
            files_browser(
                "parquet_files_selector", file_types=[("PARQUET文件", "*.parquet")]
            )
        else:
            raise ValueError(f"不支持的数据加载模式'{update_mode}'!")

        # 点击新增按钮，执行更新逻辑，主要是把同类型对单个或者多个ZIP合并成一个PARQUET文件，根据标准CSMAR数据包的ZIP里描述信息替换列
        if st.button("➕ 增加", type="primary", width="stretch"):
            if update_mode == "文件夹批量更新":
                local_parser.update_to_database_by_dir(
                    database_parquets_dir=st.session_state.get("db_dir_selector", ""),
                    target_dir=st.session_state.get("rawdata_dir_selector", ""),
                )
            elif update_mode == "指定ZIP文件更新":
                local_parser.update_to_database_by_csmar_zips(
                    database_parquets_dir=st.session_state.get("db_dir_selector", ""),
                    target_zip_files=st.session_state.get("zip_files_selector", ""),
                )
            elif update_mode == "指定CSV文件更新":
                local_parser.update_to_database_by_csvs(
                    database_parquets_dir=st.session_state.get("db_dir_selector", ""),
                    target_csv_files=st.session_state.get("csv_files_selector", ""),
                )
            elif update_mode == "指定PARQUET文件更新":
                local_parser.update_to_database_by_parquets(
                    database_parquets_dir=st.session_state.get("db_dir_selector", ""),
                    target_parquet_files=st.session_state.get(
                        "parquet_files_selector", ""
                    ),
                )
            else:
                raise ValueError(f"不支持的数据加载模式'{update_mode}'!")
            # 更新完数据包后，同步一下持久存储的st.session_state.meta_data
            with open(meta_json_path, "r", encoding="utf-8") as f:
                st.session_state.meta_data = json.load(f)

    # 数据库存在meta.json并读取到st.session_state.meta_data中，才会执行这段逻辑
    if st.session_state.meta_data:
        with st.expander("📦 数据包列表 (点击展开/折叠)", expanded=True):
            # 这里就是对meta.json内容的一个可交互展开形式、
            # 主要记录了数据库下每个数据包的文件名，数据包里面列中文名、列英文名和列描述信息
            # 每个数据包还加了个删除按钮，如果有更新的数据包可以删除后再添加新包
            for file_path, columns_info in st.session_state.meta_data.items():
                file_name = file_path.split("/")[-1]  # 简单提取文件名
                col1, col2 = st.columns([8, 1])
                # 每个文件对应一个可展开的容器
                with col1:
                    with st.expander(f"📄 {file_name} (共 {len(columns_info)} 列)"):
                        # 在展开区域里，把列信息做成表格
                        col_data = []
                        for col_key, col_info in columns_info.items():
                            col_data.append(
                                {
                                    "列名": col_key,
                                    "英文名": col_info.get("english_name", ""),
                                    "中文名": col_info.get("chinese_name", ""),
                                    "注释": col_info.get("annotation", ""),
                                }
                            )
                        df_cols = pd.DataFrame(col_data)
                        st.dataframe(df_cols, width="stretch", hide_index=True)
                with col2:
                    # 使用 popover 实现删除确认对话框
                    with st.popover("🗑️", width="stretch"):
                        st.warning(f"⚠️ 确定要删除「{file_name}」吗？")
                        st.caption("此操作不可撤销！")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button(
                                "✅ 确认删除",
                                key=f"confirm_{file_path}",
                                type="primary",
                            ):
                                local_parser.delet_from_database(
                                    database_parquets_dir=st.session_state.get(
                                        "db_dir_selector", ""
                                    ),
                                    target_parquets_files=[file_path],
                                )
                                with open(meta_json_path, "r", encoding="utf-8") as f:
                                    st.session_state.meta_data = json.load(f)
                                st.rerun()
                        with col_cancel:
                            if st.button("❌ 取消删除", key=f"cancel_{file_path}"):
                                st.toast("❌ 已取消删除")
