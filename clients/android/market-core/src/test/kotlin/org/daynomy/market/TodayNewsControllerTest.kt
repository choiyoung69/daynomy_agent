package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TodayNewsControllerTest {
    @Test fun modeResetsFiltersAndDetailAndIgnoresUnsupportedTodayPaging() = runTest {
        val s=TodaySource(); val c=NewsController(s,this)
        c.selectCategory(NewsCategory.STOCK);c.selectPage(2);c.openDetail(7)
        c.selectToday(true);runCurrent();assertTrue(s.calls.isEmpty())
        assertTrue(c.state.value.todayOnly);assertNull(c.state.value.selectedId)
        assertNull(c.state.value.category);assertEquals(1,c.state.value.page)
        c.setActive(true);runCurrent();assertEquals(listOf("today"),s.calls)
        c.selectToday(true);c.selectCategory(NewsCategory.ETF);c.selectPage(2);runCurrent()
        assertEquals(listOf("today"),s.calls);assertEquals(1,c.state.value.page)
        c.openDetail(42);runCurrent();c.closeDetail()
        assertTrue(c.state.value.todayOnly);assertEquals(42L,(c.state.value.list as LoadState.Ready).value.items.single().id)
        c.selectToday(false);runCurrent();assertEquals("all:null:1",s.calls.last())
        assertFalse(c.state.value.todayOnly);c.close()
    }
    @Test fun lateNormalAndTodayResponsesCannotOverwriteNewMode() = runTest {
        val all=CompletableDeferred<NewsPage>();val today=CompletableDeferred<NewsPage>()
        val s=TodaySource();s.listAnswer={_,_->withContext(NonCancellable){all.await()}}
        val c=NewsController(s,this);c.setActive(true);runCurrent();c.selectToday(true);runCurrent()
        all.complete(todayPage(1));runCurrent()
        try {assertEquals(42L,(c.state.value.list as LoadState.Ready).value.items.single().id)
            s.listAnswer={_,_->todayPage(1)};c.selectToday(false);runCurrent()
            s.todayAnswer={withContext(NonCancellable){today.await()}};c.selectToday(true);runCurrent()
            c.selectToday(false);runCurrent();today.complete(todayPage(42));runCurrent()
            assertEquals(1L,(c.state.value.list as LoadState.Ready).value.items.single().id)
        } finally {all.complete(todayPage(1));today.complete(todayPage(42));c.close()}
    }
    @Test fun errorIsSafeAndOnlyExplicitRetryLoadsEmptyToday() = runTest {
        val s=TodaySource();s.todayAnswer={throw IOException("private-body")};val c=NewsController(s,this)
        c.setActive(true);runCurrent();c.selectToday(true);runCurrent()
        try {assertTrue(c.state.value.list is LoadState.Failed)
            assertFalse((c.state.value.list as LoadState.Failed).message.contains("private-body"))
            assertEquals(1,s.calls.count{it=="today"});c.selectToday(true);runCurrent()
            assertEquals(1,s.calls.count{it=="today"})
            s.todayAnswer={todayPage(42).copy(items=emptyList(),totalElements=0,totalPages=0,hasNext=false)}
            c.retryList();runCurrent();assertTrue((c.state.value.list as LoadState.Ready).value.items.isEmpty())
            assertTrue(c.state.value.todayOnly)
        } finally {c.close()}
    }
    @Test fun inactiveAndCloseCancelTodayWithoutLosingMode() = runTest {
        var cancelled=false;val s=TodaySource();s.todayAnswer={try {awaitCancellation()} finally {cancelled=true}}
        val c=NewsController(s,this);c.selectToday(true);c.setActive(true);runCurrent();c.setActive(false);runCurrent()
        try {assertTrue(cancelled);assertEquals(LoadState.Idle,c.state.value.list)
            s.todayAnswer={todayPage(42)};c.setActive(true);runCurrent();assertTrue(c.state.value.todayOnly)
            c.close();val count=s.calls.size;c.selectToday(false);c.retryList();c.setActive(true);runCurrent()
            assertEquals(count,s.calls.size);assertTrue(c.state.value.todayOnly)
        } finally {c.close()}
    }
    @Test fun switchedModeRejectsLateDetailFailure() = runTest {
        val gate=CompletableDeferred<Unit>();val s=TodaySource();s.detailAnswer={withContext(NonCancellable){gate.await()};throw IOException("late")}
        val c=NewsController(s,this);c.setActive(true);c.selectToday(true);runCurrent();c.openDetail(42);runCurrent()
        c.selectToday(false);runCurrent();gate.complete(Unit);runCurrent()
        try {assertNull(c.state.value.selectedId);assertEquals(LoadState.Idle,c.state.value.detail)}finally{gate.complete(Unit);c.close()}
    }
}
private fun todayPage(id:Long)=NewsPage(listOf(NewsListItem(id,"news",NewsCategory.STOCK,null,null)),1,9,2,12,true)
private class TodaySource:NewsSource {
    val calls=mutableListOf<String>()
    var listAnswer:suspend(NewsCategory?,Int)->NewsPage={_,_->todayPage(1)}
    var todayAnswer:suspend()->NewsPage={todayPage(42)}
    var detailAnswer:suspend(Long)->NewsDetail={NewsDetail(it,"detail",NewsCategory.STOCK,"date",listOf("body"),null,null,emptyList())}
    override suspend fun list(category:NewsCategory?,page:Int,size:Int):NewsPage{calls+="all:$category:$page";return listAnswer(category,page)}
    override suspend fun today():NewsPage{calls+="today";return todayAnswer()}
    override suspend fun detail(newsId:Long)=detailAnswer(newsId)
}
