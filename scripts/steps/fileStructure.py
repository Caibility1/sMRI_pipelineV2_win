import os

def generate_tree(target_path, depth_limit=3, current_depth=0):
    """
    递归生成文件夹树状结构字符串
    """
    if current_depth > depth_limit:
        return ""
    
    output = ""
    # 获取当前目录下所有文件夹和文件
    try:
        items = os.listdir(target_path)
    except PermissionError:
        return indent + "[Permission Denied]\n"

    # 排序：文件夹在前，文件在后
    items.sort(key=lambda x: (not os.path.isdir(os.path.join(target_path, x)), x))

    for i, item in enumerate(items):
        path = os.path.join(target_path, item)
        is_last = (i == len(items) - 1)
        
        # 构造分支符号
        prefix = "└── " if is_last else "├── "
        output += "    " * current_depth + prefix + item + "\n"
        
        # 递归处理子目录
        if os.path.isdir(path):
            output += generate_tree(path, depth_limit, current_depth + 1)
            
    return output

# ================= 配置区 =================
# 1. 设置你要遍历的文件夹路径
#TARGET_FOLDER = r"D:\master\project\data0"
TARGET_FOLDER = r"D:\University\master\QC2026\0_code"
# 2. 设置遍历深度，防止文件夹太多导致 PPT 装不下
MAX_DEPTH = 666
# 3. 输出文件名
OUTPUT_FILE = "folder_structure.txt"
# ==========================================

if __name__ == "__main__":
    if os.path.exists(TARGET_FOLDER):
        tree_str = f"{os.path.basename(TARGET_FOLDER)}/\n" + generate_tree(TARGET_FOLDER, MAX_DEPTH)
        
        # 打印到控制台预览
        print(tree_str)
        
        # 保存到本地文件
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(tree_str)
        print(f"\n[完成] 结构已保存至: {OUTPUT_FILE}")
    else:
        print("错误：找不到指定的文件夹路径。")