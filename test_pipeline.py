from det.pipeline.service import PipelineService

service = PipelineService()
store = service._load()
print(store.projects)
