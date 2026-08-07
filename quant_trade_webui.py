import streamlit as st
import os
import json
import pandas as pd
from .quant_trade_webui_deps import *




def qtw_database_manager():
    if 'meta_data' not in st.session_state:
        st.session_state.meta_data = None
    if 'show_expander' not in st.session_state:
        st.session_state.show_expander = False

    db_dir = st.sidebar.text_input(
        label="本地数据库文件夹目录:", value="E:/BenQTrade/ben-qtrade/database"
    )
    if not db_dir or not os.path.isdir(db_dir):
        st.warning(f"{db_dir}不是有效文件夹路径，请设置有效的数据库文件夹路径")
        st.stop()
    meta_json_path = os.path.join(db_dir, "meta.json")
    # 使用回调函数处理同步按钮
    def sync_database_callback():
        if os.path.exists(meta_json_path):
            with open(meta_json_path, "r", encoding="utf-8") as f:
                st.session_state.meta_data = json.load(f)
            st.session_state.show_expander = True
            st.sidebar.success("✅ 解析成功！")
        else:
            st.sidebar.error(f"找不到 meta.json 文件: {meta_json_path}")   

    sync_button_flag = st.sidebar.button("🔄 同步", width="stretch",on_click=sync_database_callback)

    # meta_json_path = META_PATH = os.path.join(db_dir, "meta.json")
    mode = st.sidebar.selectbox(
        label="更新数据库", options=["文件夹批量更新", "指定文件更新"]
    )
    if mode == "文件夹批量更新":
        db_dir = st.sidebar.text_input(
            label="原始数据文件夹:", value="E:/BenQTrade/CSMAR金融数据库原始数据集"
        )
        if not db_dir or not os.path.isdir(db_dir):
            st.warning(f"{db_dir}不是有效文件夹路径，请设置有效的原始数据文件夹路径")
            st.stop()
    elif mode == "指定文件更新":
        db_files = st.sidebar.file_uploader(
            label="指定数据文件", accept_multiple_files=True, type=["zip"]
        )
    else:
        raise ValueError(f"不支持的数据加载模式'{mode}'!")
    
    def add_database_callback():
        # 这里添加增加逻辑
        st.session_state.show_expander = True
        # 如果需要在增加后刷新数据，可以重新加载
        if os.path.exists(meta_json_path):
            with open(meta_json_path, "r", encoding="utf-8") as f:
                st.session_state.meta_data = json.load(f)
    add_button_flag = st.sidebar.button("➕ 增加", type="primary", width="stretch",on_click=add_database_callback)
    
    def confirm_delete_callback(file_path, confirmed=False):
        if confirmed:
            if file_path in st.session_state.meta_data:
                # 实际删除逻辑
                del st.session_state.meta_data[file_path]
                # 这里可以添加实际删除文件的逻辑
                st.toast(f"✅ 已成功删除: {file_path.split('/')[-1]}")
                if not st.session_state.meta_data:
                    st.session_state.show_expander = False
                # 强制刷新
                st.rerun()
        else:
            st.toast("❌ 已取消删除")

    if st.session_state.show_expander and st.session_state.meta_data:
        # with open(meta_json_path, "r", encoding="utf-8") as f:
        #     meta_data = json.load(f)
        # 核心部分：用一个循环，为每个文件生成一个 st.expander
        with st.expander("📦 数据包列表 (点击展开/折叠)", expanded=True):
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
                    # 使用 popover 实现确认对话框
                    with st.popover("🗑️", use_container_width=True):
                        st.warning(f"⚠️ 确定要删除「{file_name}」吗？")
                        st.caption("此操作不可撤销！")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button("✅ 确认删除", key=f"confirm_{file_path}", type="primary"):
                                confirm_delete_callback(file_path, confirmed=True)
                        with col_cancel:
                            if st.button("❌ 取消删除", key=f"cancel_{file_path}"):
                                confirm_delete_callback(file_path, confirmed=False)
    elif st.session_state.meta_data is None:
        # 首次加载时的提示
        st.info("👈 请点击侧边栏的 '🔄 同步' 按钮加载数据")


def qtw_data_viz():
    st.title("📊 数据可视化")
    st.write("这里实现你的数据可视化功能")


def qtw_backtest():
    st.title("📈 策略回测")
    st.write("这里实现你的量化回测功能")


def run_quant_trade_webui():

    # 配置顶部导航
    pg = st.navigation([
        st.Page(qtw_database_manager, title="数据库管理", icon=":material/folder:"),
        st.Page(qtw_data_viz, title="数据可视化", icon=":material/bar_chart:"),
        st.Page(qtw_backtest, title="策略回测", icon=":material/timeline:"),
    ], position="top")  # 关键参数：导航放在顶部

    pg.run()  # 执行当前选中的页面


if __name__ == "__main__":
    run_quant_trade_webui()
