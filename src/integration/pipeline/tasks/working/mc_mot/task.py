"""MC-MOT integration stage."""
from __future__ import annotations

from smart_workflow import BaseTask, TaskContext, TaskResult

from .engine import MCMOTEngine
from integration.mcmot.visualization.map_overlay import OverlayResult


class MCMOTTask(BaseTask):
    name = "mc_mot"

    def run(self, context: TaskContext) -> TaskResult:
        events = context.get_resource("edge_events") or []
        if not context.config.mcmot_enabled:
            context.logger.info("MC-MOT 已停用，略過 %d 筆事件", len(events))
            context.set_resource("mc_mot_tracked", [])
            context.set_resource("mc_mot_global_objects", [])
            return TaskResult(status="mc_mot_skipped")

        engine: MCMOTEngine = context.require_resource("mcmot_engine")
        if not events:
            context.logger.info("MC-MOT 沒有可處理的事件")
            context.set_resource("mc_mot_tracked", [])
            context.set_resource("mc_mot_global_objects", engine.process_events([]).global_objects)
            return TaskResult(status="mc_mot_done", payload={"events": 0, "tracked": 0, "global_objects": 0})
        
        result = engine.process_events(events)
        tracked = result.tracked_objects
        global_objects = result.global_objects
        context.set_resource("mc_mot_tracked", tracked)
        context.set_resource("mc_mot_global_objects", global_objects)

        self._maybe_render_global_map(context, global_objects, tracked)

        context.logger.info(
            "MC-MOT 處理 %d 筆事件，產生 %d 筆追蹤結果，維護 %d 筆全域物件",
            len(events),
            len(tracked),
            len(global_objects),
        )
        return TaskResult(
            status="mc_mot_done",
            payload={"events": len(events), "tracked": len(tracked), "global_objects": len(global_objects)},
        )

    def _maybe_render_global_map(self, context: TaskContext, global_objects, tracked_objects) -> None:
        renderer = context.get_resource("global_map_renderer")
        if renderer is None:
            return
        try:
            result: OverlayResult | None = renderer.render(global_objects, tracked_objects or [])
            if result and result.image_path:
                context.set_resource("global_map_snapshot", str(result.image_path))
        except Exception as exc:  # pylint: disable=broad-except
            context.logger.warning("全局地圖可視化失敗：%s", exc)
