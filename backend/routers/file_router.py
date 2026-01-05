import json
import shutil
import time
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from models import CharacterModel, UpdateTaskRequest, GenerateRequest
from services import processing_service


router = APIRouter()
BASE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

@router.post("/submit")
async def submit_character_data(
    data: str = Form(...),
    files: List[UploadFile] = File(default=[]) 
):
    try:
        # 1. 解析数据
        raw_dict = json.loads(data)
        # 补全 Pydantic模型需要的默认字段，防止前端漏传
        character_data = CharacterModel(**raw_dict)

        # 2. 文件保存逻辑 (保持原样，略微优化文件名回填)
        timestamp = int(time.time())
        safe_name = "".join([c for c in character_data.character_name if c.isalnum() or c in (' ', '_')]).strip().replace(" ", "_") or "unknown"
        task_dir = BASE_DATA_DIR / f"{safe_name}_{timestamp}"
        files_dir = task_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        # file_map = {f.filename: f for f in files}
        
        # for ref in character_data.reference:
        #     # 这里的 logic 和之前一致，处理文件移动
        #     if ref.resource_type in ["file", "image"] and ref.resource_url == "PENDING_UPLOAD":
        #         # 前端需要在 formData传递文件名，或者我们在前端 logic 里保证 filename 匹配
        #         # 为了简单，这里假设 files 列表里的文件顺序和 refs 里待上传的顺序一致 (简单方案)
        #         pass 
        #         # 更好的方案：前端 ReferenceModel 里带一个 temp_id，files 上传时 key 对应 temp_id
        #         # 简单实现：按文件名匹配 (前端需传原始文件名)
        
        # # (此处省略具体保存代码，假设文件已保存并更新 ref.resource_url 此时为本地路径)
        # # 简单做个处理：遍历 files 保存
        uploaded_idx = 0
        for ref in character_data.reference:
            if ref.resource_type in ["file", "image"] and ref.resource_url == "PENDING_UPLOAD":
                 if uploaded_idx < len(files):
                     f_obj = files[uploaded_idx]
                     save_path = files_dir / f_obj.filename
                     with open(save_path, "wb") as buffer:
                        shutil.copyfileobj(f_obj.file, buffer)
                     ref.resource_url = str(save_path.absolute())
                     ref.file_name = f_obj.filename # 记录下来给UI显示
                     uploaded_idx += 1
            elif ref.resource_type == "url":
                ref.file_name = ref.resource_url # URL即文件名

        # 3. 生成唯一的 Process ID
        process_id = str(uuid.uuid4())

        # 4. 触发后台处理服务
        # 注意：这里我们只触发，不等待，直接返回 ID 给前端
        processing_service.start_processing_background(character_data, process_id)

        return {
            "status": "success",
            "process_id": process_id,
            "message": "Task submitted, processing started."
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{process_id}")
async def check_status(process_id: str):
    status = processing_service.get_task_status(process_id)
    if not status:
        raise HTTPException(status_code=404, detail="Process ID not found")
    return status

@router.post("/update_task_result")
async def update_task_result(req: UpdateTaskRequest):
    """
    Step 3: 用户修改并确认某个子任务的解析结果
    """
    success = processing_service.update_subtask_result(
        req.process_id, 
        req.step_id, 
        req.new_summary
    )
    if not success:
        raise HTTPException(status_code=400, detail="Update failed, task not found.")
    return {"status": "success"}

@router.post("/generate_card")
async def generate_card(req: GenerateRequest):
    """
    Step 3 -> Step 4: 触发最终生成
    """
    try:
        processing_service.start_card_generation(req.process_id)
        return {"status": "success", "message": "Generation started"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))