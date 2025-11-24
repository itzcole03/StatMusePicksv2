from backend.services.llm_feature_service import LLMFeatureService

def tf(name):
    return 'Player had a routine practice, nothing notable.'

s=LLMFeatureService()
print('default_model=',s.default_model)
print(s.fetch_news_and_extract('PlayerX','test',tf))
print(s.fetch_news_and_extract('PlayerX','test',tf))
