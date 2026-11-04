package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import okhttp3.mockwebserver.*
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith
import java.util.concurrent.CopyOnWriteArrayList

@RunWith(AndroidJUnit4::class)
class NewsKeywordsScreenTest {
    @get:Rule val compose=createEmptyComposeRule()
    private lateinit var server:MockWebServer
    private val requests=CopyOnWriteArrayList<String>()
    @Volatile private var failing=false
    @Volatile private var empty=false
    @Before fun setup(){
        server=MockWebServer();server.dispatcher=object:Dispatcher(){
            override fun dispatch(request:RecordedRequest):MockResponse {
                val path=request.path.orEmpty();requests+=path
                return when(path){
                    "/api/news?page=1&size=6"->json("""{"items":[{"id":42,"title":"경제 뉴스","category":"STOCK","imageUrl":null,"publishedAt":null}],"page":1,"size":6,"totalPages":1,"totalElements":1,"hasNext":false}""")
                    "/api/news/42"->json("""{"id":42,"title":"경제 상세","category":"STOCK","publishedAt":"2026-11-04","content":"상세 본문 유지","sources":[]}""")
                    "/api/news/42/keywords"->if(failing)json("""{"message":"private-body"}""").setResponseCode(503) else json(if(empty)"""{"keywords":[]}""" else """{"keywords":[{"category":"POLICY","keyword":"기준금리","points":["금리 뜻","기사 속 맥락","확인 제안"],"definition":"금리 뜻","context":"기사 속 맥락","watchPoint":"확인 제안"}]}""")
                    else->MockResponse().setResponseCode(404)
                }
            }
        };server.start()
    }
    @After fun stop(){server.shutdown()}
    private fun json(body:String)=MockResponse().setHeader("Content-Type","application/json").setBody(body)
    private fun launch():ActivityScenario<MainActivity>{val c=ApplicationProvider.getApplicationContext<Context>();return ActivityScenario.launch(Intent(c,MainActivity::class.java).putExtra("base_url",server.url("/").toString()))}
    private fun await(tag:String){compose.waitUntil(8000){compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty()}}
    private fun open(){await("tab-news");compose.onNodeWithTag("tab-news").performClick();await("news-item-42");compose.onNodeWithTag("news-item-42").performScrollTo().performClick();await("news-detail")}
    @Test fun keywordsSurviveRotationAndClearOnBack(){launch().use{scenario->
        open();await("news-keywords");compose.onNodeWithText("기준금리 · 정책").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("뜻: 금리 뜻").assertExists();compose.onNodeWithText("기사 속 의미: 기사 속 맥락").assertExists();compose.onNodeWithText("확인할 점: 확인 제안").assertExists()
        assertEquals(1,requests.count{it=="/api/news/42/keywords"})
        scenario.recreate();await("news-keywords");compose.onNodeWithText("기준금리 · 정책").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("news-back").performScrollTo().performClick();await("news-item-42");compose.onNodeWithTag("news-keywords").assertDoesNotExist()
        assertEquals(2,requests.count{it=="/api/news/42/keywords"})
    }}
    @Test fun failureKeepsArticleAndRetryShowsEmpty(){failing=true;launch().use{
        open();await("news-keywords-error");compose.onNodeWithText("상세 본문 유지").assertExists();compose.onNodeWithText("private-body").assertDoesNotExist()
        assertEquals(1,requests.count{it=="/api/news/42/keywords"});failing=false;empty=true
        compose.onNodeWithTag("news-keywords-retry").performScrollTo().performClick();await("news-keywords-empty")
        compose.onNodeWithTag("news-keywords-empty").performScrollTo().assertTextEquals("이 뉴스에 등록된 키워드가 없습니다.")
        assertEquals(2,requests.count{it=="/api/news/42/keywords"})
    }}
}
