# نموذج أولي لخوارزمية المطابقة الذكية في In Work (AI Matching Core)
def match_provider_to_client(client_location: dict, providers: list) -> dict:
    """
    تقوم هذه الخوارزمية باختيار أفضل حرفي بناءً على المسافة الجغرافية والتقييم.
    تم تصميمها لتكون النواة الأساسية لربط الخدمات في منصة In Work.
    """
    if not providers:
        return None
    
    # اختيار الحرفي الأقرب والأعلى تقييماً كمعيار مبدئي ذكي
    best_match = min(providers, key=lambda p: (p['distance_km'], -p['rating']))
    return best_match

if __name__ == "__main__":
    print("In Work AI Matching Engine Loaded Successfully 🟢")
