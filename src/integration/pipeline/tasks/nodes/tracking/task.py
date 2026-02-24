"""MC-MOT integration stage."""
from __future__ import annotations

from smart_workflow import BaseTask, TaskContext, TaskResult, TaskError

from integration.mcmot.visualization.map_overlay import GlobalMapRenderer, OverlayResult
from integration.pipeline.tasks.nodes.tracking.engine import MCMOTEngine
from .handler import BaseTrackingHandler, DefaultTrackingHandler, TrackingResult, load_tracking_handler


class MCMOTTask(BaseTask):
    name = "mc_mot"

    def __init__(self, context: TaskContext | None = None) -> None:
        self._handler: BaseTrackingHandler | None = None

    def run(self, context: TaskContext) -> TaskResult:
        if self._handler is None:
            if context is not None:
                self._ensure_engine(context)
            self._handler = self._init_handler(context)
        events = context.get_resource("edge_events") or []
        if not context.config.mcmot_enabled:
            context.logger.info("MC-MOT 已停用，略過 %d 筆事件", len(events))
            context.set_resource("mc_mot_tracked", [])
            context.set_resource("mc_mot_global_objects", [])
            return TaskResult(status="mc_mot_skipped")

        result = self._handler.process(context, events)
        context.set_resource("mc_mot_tracked", result.tracked_objects)
        context.set_resource("mc_mot_global_objects", result.global_objects)

        self._maybe_render_global_map(context, result.global_objects, result.tracked_objects)

        context.logger.info(
            "MC-MOT 處理 %d 筆事件，產生 %d 筆追蹤結果，維護 %d 筆全域物件",
            result.processed_events,
            len(result.tracked_objects),
            len(result.global_objects),
        )
        return TaskResult(
            status="mc_mot_done",
            payload={
                "events": result.processed_events,
                "tracked": len(result.tracked_objects),
                "global_objects": len(result.global_objects),
            },
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

    def _ensure_engine(self, context: TaskContext) -> None:
        if not context.config.mcmot_enabled:
            return
        if context.get_resource("mcmot_engine") is None:
            if context.config.mcmot is None:
                raise TaskError("MC-MOT 已啟用但設定未載入")
            engine = MCMOTEngine(config=context.config.mcmot, logger=context.logger)
            context.set_resource("mcmot_engine", engine)
            context.logger.info("MC-MOT engine initialized")

        if context.get_resource("global_map_renderer") is None:
            vis_cfg = getattr(context.config, "global_map_visualization", None)
            if vis_cfg and vis_cfg.enabled:
                map_cfg = context.config.mcmot.map if context.config.mcmot else None
                if map_cfg is None:
                    context.logger.warning("啟用了全局可視化但 mcmot map 未設定")
                    return
                renderer = GlobalMapRenderer(
                    map_cfg=map_cfg,
                    vis_cfg=vis_cfg,
                    logger=context.logger,
                    camera_configs=context.config.mcmot.cameras,
                )
                context.set_resource("global_map_renderer", renderer)
                context.logger.info("Global map renderer initialized")

    def _init_handler(self, context: TaskContext | None) -> BaseTrackingHandler:
        cfg = getattr(context.config, "tracking_task", None) if context else None
        handler_path = getattr(cfg, "engine_class", None) if cfg else None
        if not handler_path:
            return DefaultTrackingHandler(context=context)
        try:
            handler_cls = load_tracking_handler(handler_path)
        except Exception as exc:  # pylint: disable=broad-except
            raise TaskError(f"無法載入 Tracking Handler：{handler_path}") from exc
        try:
            return handler_cls(context=context)
        except TypeError:
            try:
                return handler_cls()
            except TypeError as exc:  # pragma: no cover
                raise TaskError(f"Tracking Handler {handler_path} 無法初始化") from exc
