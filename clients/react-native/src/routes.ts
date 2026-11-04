export const routes:Record<string,{path:string;method:string;csrf:boolean}>={
  "news": {
    "path": "/api/news",
    "method": "GET",
    "csrf": false
  },
  "today": {
    "path": "/api/news/today",
    "method": "GET",
    "csrf": false
  },
  "newsDetail": {
    "path": "/api/news/{id}",
    "method": "GET",
    "csrf": false
  },
  "keywords": {
    "path": "/api/news/{id}/keywords",
    "method": "GET",
    "csrf": false
  },
  "marketAnalysis": {
    "path": "/api/news/{id}/market-analysis",
    "method": "GET",
    "csrf": false
  },
  "contentSearch": {
    "path": "/api/search/contents",
    "method": "GET",
    "csrf": false
  },
  "newsSearch": {
    "path": "/api/search/news",
    "method": "GET",
    "csrf": false
  },
  "contents": {
    "path": "/api/contents",
    "method": "GET",
    "csrf": false
  },
  "assetContents": {
    "path": "/api/assets/{id}/contents",
    "method": "GET",
    "csrf": false
  },
  "people": {
    "path": "/api/people",
    "method": "GET",
    "csrf": false
  },
  "fx": {
    "path": "/api/exchange-rates/usd-krw",
    "method": "GET",
    "csrf": false
  },
  "profile": {
    "path": "/api/users/me",
    "method": "GET",
    "csrf": false
  },
  "updateProfile": {
    "path": "/api/users/me",
    "method": "PATCH",
    "csrf": true
  },
  "withdraw": {
    "path": "/api/users/me",
    "method": "DELETE",
    "csrf": true
  },
  "logout": {
    "path": "/api/auth/logout",
    "method": "POST",
    "csrf": true
  },
  "feedback": {
    "path": "/api/feedback",
    "method": "POST",
    "csrf": true
  },
  "portfolio": {
    "path": "/api/users/me/portfolio",
    "method": "GET",
    "csrf": false
  },
  "calculate": {
    "path": "/api/portfolio/calculate",
    "method": "POST",
    "csrf": true
  },
  "createTrade": {
    "path": "/api/portfolio/transactions",
    "method": "POST",
    "csrf": true
  },
  "updateTrade": {
    "path": "/api/portfolio/transactions/{id}",
    "method": "PATCH",
    "csrf": true
  },
  "deleteTrade": {
    "path": "/api/portfolio/transactions/{id}",
    "method": "DELETE",
    "csrf": true
  },
  "updateHolding": {
    "path": "/api/users/me/portfolio/holdings/{id}",
    "method": "PATCH",
    "csrf": true
  },
  "deleteHolding": {
    "path": "/api/users/me/portfolio/holdings/{id}",
    "method": "DELETE",
    "csrf": true
  },
  "histories": {
    "path": "/api/portfolio/histories",
    "method": "GET",
    "csrf": false
  },
  "performance": {
    "path": "/api/users/me/portfolio/performance",
    "method": "GET",
    "csrf": false
  },
  "calendar": {
    "path": "/api/users/me/investment-calendar",
    "method": "GET",
    "csrf": false
  },
  "guestCalendar": {
    "path": "/api/investment-calendar",
    "method": "POST",
    "csrf": true
  },
  "guestAnalysis": {
    "path": "/api/portfolio/analysis",
    "method": "POST",
    "csrf": false
  },
  "analysis": {
    "path": "/api/users/me/portfolio/analysis",
    "method": "GET",
    "csrf": false
  },
  "updateAnalysis": {
    "path": "/api/users/me/portfolio/analysis",
    "method": "POST",
    "csrf": true
  },
  "refreshAnalysis": {
    "path": "/api/users/me/portfolio/analysis/refresh",
    "method": "POST",
    "csrf": true
  },
  "analysisHistory": {
    "path": "/api/users/me/portfolio/analysis/history",
    "method": "GET",
    "csrf": false
  },
  "mobileExchange": {
    "path": "/api/auth/mobile/exchange",
    "method": "POST",
    "csrf": false
  },
  "adminNews": {
    "path": "/api/admin/news",
    "method": "GET",
    "csrf": false
  },
  "adminNewsDetail": {
    "path": "/api/admin/news/{id}",
    "method": "GET",
    "csrf": false
  },
  "adminCreateNews": {
    "path": "/api/admin/news",
    "method": "POST",
    "csrf": true
  },
  "adminUpdateNews": {
    "path": "/api/admin/news/{id}",
    "method": "PUT",
    "csrf": true
  },
  "adminDeleteNews": {
    "path": "/api/admin/news/{id}",
    "method": "DELETE",
    "csrf": true
  },
  "adminPublishNews": {
    "path": "/api/admin/news/{id}/publish",
    "method": "POST",
    "csrf": true
  },
  "adminRejectNews": {
    "path": "/api/admin/news/{id}/reject",
    "method": "POST",
    "csrf": true
  },
  "adminGenerateKorea": {
    "path": "/api/admin/news/generate/economy/korea",
    "method": "POST",
    "csrf": true
  },
  "adminGenerateUS": {
    "path": "/api/admin/news/generate/economy/us",
    "method": "POST",
    "csrf": true
  },
  "adminImageSearch": {
    "path": "/api/admin/news/image-search",
    "method": "GET",
    "csrf": false
  },
  "adminGenerateImage": {
    "path": "/api/admin/news/{id}/generate-image",
    "method": "POST",
    "csrf": true
  },
  "adminFeedbacks": {
    "path": "/api/admin/feedbacks",
    "method": "GET",
    "csrf": false
  },
  "adminFeedback": {
    "path": "/api/admin/feedbacks/{id}",
    "method": "GET",
    "csrf": false
  },
  "adminUpdateFeedback": {
    "path": "/api/admin/feedbacks/{id}",
    "method": "PATCH",
    "csrf": true
  },
  "adminDeleteFeedback": {
    "path": "/api/admin/feedbacks/{id}",
    "method": "DELETE",
    "csrf": true
  },
  "adminAssetContents": {
    "path": "/api/admin/assets/{id}/contents",
    "method": "GET",
    "csrf": false
  },
  "adminCreateContent": {
    "path": "/api/admin/assets/{id}/contents",
    "method": "POST",
    "csrf": true
  },
  "adminDeleteContent": {
    "path": "/api/admin/assets/{id}/contents/{secondaryId}",
    "method": "DELETE",
    "csrf": true
  },
  "adminYoutubeSearch": {
    "path": "/api/admin/assets/{id}/contents/youtube-search",
    "method": "GET",
    "csrf": false
  },
  "adminSocialSearch": {
    "path": "/api/admin/assets/{id}/contents/social-search",
    "method": "GET",
    "csrf": false
  },
  "adminPeople": {
    "path": "/api/admin/people",
    "method": "GET",
    "csrf": false
  },
  "adminCreatePerson": {
    "path": "/api/admin/people",
    "method": "POST",
    "csrf": true
  },
  "adminUpdatePerson": {
    "path": "/api/admin/people/{id}",
    "method": "PUT",
    "csrf": true
  },
  "adminDeletePerson": {
    "path": "/api/admin/people/{id}",
    "method": "DELETE",
    "csrf": true
  },
  "adminSearchPosts": {
    "path": "/api/admin/people/{id}/posts/search",
    "method": "GET",
    "csrf": false
  },
  "adminCreatePost": {
    "path": "/api/admin/people/{id}/posts",
    "method": "POST",
    "csrf": true
  },
  "adminDeletePost": {
    "path": "/api/admin/people/{id}/posts/{secondaryId}",
    "method": "DELETE",
    "csrf": true
  },
  "adminCandidates": {
    "path": "/api/admin/people/{id}/post-candidates",
    "method": "GET",
    "csrf": false
  },
  "adminCollectPosts": {
    "path": "/api/admin/people/{id}/post-candidates/collect",
    "method": "POST",
    "csrf": true
  },
  "adminApproveCandidate": {
    "path": "/api/admin/people/{id}/post-candidates/{secondaryId}/approve",
    "method": "POST",
    "csrf": true
  },
  "adminRejectCandidate": {
    "path": "/api/admin/people/{id}/post-candidates/{secondaryId}/reject",
    "method": "POST",
    "csrf": true
  },
  "adminBulkApprove": {
    "path": "/api/admin/people/{id}/post-candidates/bulk-approve",
    "method": "POST",
    "csrf": true
  },
  "adminBulkReject": {
    "path": "/api/admin/people/{id}/post-candidates/bulk-reject",
    "method": "POST",
    "csrf": true
  },
  "adminAllCandidates": {
    "path": "/api/admin/people/post-candidates",
    "method": "GET",
    "csrf": false
  },
  "adminAllBulkApprove": {
    "path": "/api/admin/people/post-candidates/bulk-approve",
    "method": "POST",
    "csrf": true
  },
  "adminAllBulkReject": {
    "path": "/api/admin/people/post-candidates/bulk-reject",
    "method": "POST",
    "csrf": true
  },
  "syncKR": {
    "path": "/api/admin/stocks/sync",
    "method": "POST",
    "csrf": true
  },
  "syncKRPrices": {
    "path": "/api/admin/stocks/prices/sync",
    "method": "POST",
    "csrf": true
  },
  "backfill": {
    "path": "/api/admin/stocks/prices/backfill",
    "method": "POST",
    "csrf": true
  },
  "syncUS": {
    "path": "/api/admin/stocks/us/sync",
    "method": "POST",
    "csrf": true
  },
  "syncUSPrices": {
    "path": "/api/admin/stocks/us/prices/sync",
    "method": "POST",
    "csrf": true
  },
  "stocks": {
    "path": "/api/stocks",
    "method": "GET",
    "csrf": false
  },
  "stockPrice": {
    "path": "/api/stocks/{id}/price",
    "method": "GET",
    "csrf": false
  }
};
