package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import okhttp3.mockwebserver.*
import java.util.concurrent.CopyOnWriteArrayList
import org.junit.*
import org.junit.Assert.*
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TodayNewsScreenTest {
 @get:Rule val compose=createEmptyComposeRule()
 private lateinit var server:MockWebServer
 private val requests=CopyOnWriteArrayList<RecordedRequest>()
 @Volatile private var fails=false
 @Volatile private var empty=false
 @Before fun setup(){server=MockWebServer();server.dispatcher=object:Dispatcher(){override fun dispatch(request:RecordedRequest):MockResponse{
  requests+=request
  return when(request.requestUrl?.encodedPath){
   "/api/news"->json(page(1,false))
   "/api/news/today"->if(fails)json("""{"message":"private-body"}""").setResponseCode(503) else json(page(42,true))
   "/api/news/42"->json("""{"id":42,"title":"오늘 상세","category":"STOCK","publishedAt":"2099-01-01T00:00:00Z","content":"오늘 본문","sources":[]}""")
   else->MockResponse().setResponseCode(404)
  }
 }};server.start()}
 @After fun stop(){server.shutdown()}
 private fun json(body:String)=MockResponse().setHeader("Content-Type","application/json").setBody(body)
 private fun page(id:Int,today:Boolean):String {
  val items=if(today&&empty)"" else """{"id":$id,"title":"뉴스 $id","category":"STOCK","imageUrl":null,"publishedAt":"2099-01-01T00:00:00Z"}"""
  return """{"items":[$items],"page":1,"size":${if(today)9 else 6},"totalPages":${if(empty)0 else 2},"totalElements":${if(empty)0 else 12},"hasNext":${!empty}}"""
 }
 private fun launch():ActivityScenario<MainActivity>{val c=ApplicationProvider.getApplicationContext<Context>();return ActivityScenario.launch(Intent(c,MainActivity::class.java).putExtra("base_url",server.url("/").toString()))}
 private fun await(tag:String){compose.waitUntil(8000){compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty()}}
 @Test fun todayDetailBackRotationAndAllMode(){launch().use{scenario->
  await("tab-news");compose.onNodeWithTag("tab-news").performClick();await("news-mode-today")
  compose.onNodeWithTag("news-mode-today").performScrollTo().performClick();await("news-item-42")
  compose.onNodeWithTag("category-ALL").assertDoesNotExist();compose.onNodeWithTag("news-next").assertDoesNotExist()
  compose.onNodeWithTag("news-item-42").performScrollTo().performClick();await("news-detail")
  compose.onNodeWithTag("news-back").performScrollTo().performClick();await("news-item-42")
  scenario.recreate();await("news-item-42");compose.onNodeWithTag("news-mode-today").assertIsSelected()
  compose.onNodeWithTag("news-mode-all").performScrollTo().performClick();await("news-item-1")
  assertTrue(requests.any{it.path=="/api/news/today"});assertFalse(requests.any{it.path?.startsWith("/api/news/today?")==true})
 }}
 @Test fun explicitRetryRecoversToTodayEmpty(){fails=true;launch().use{
  await("tab-news");compose.onNodeWithTag("tab-news").performClick();await("news-mode-today")
  compose.onNodeWithTag("news-mode-today").performScrollTo().performClick();await("news-error")
  compose.onNodeWithText("private-body").assertDoesNotExist();fails=false;empty=true
  compose.onNodeWithTag("news-retry").performScrollTo().performClick();await("news-empty")
  compose.onNodeWithTag("news-empty").assertTextContains("오늘 발행된 뉴스가 없습니다.")
  assertEquals(2,requests.count{it.path=="/api/news/today"})
 }}
}
