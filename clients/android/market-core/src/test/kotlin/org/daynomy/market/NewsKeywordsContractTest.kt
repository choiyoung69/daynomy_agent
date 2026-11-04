package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

private const val KEYWORD = """{"category":"POLICY","keyword":"금리 😀","points":["뜻","맥락","확인"],"definition":"뜻","context":"맥락","watchPoint":"확인"}"""
private fun body(row: String = KEYWORD) = """{"keywords":[$row]}"""

@OptIn(ExperimentalCoroutinesApi::class)
class NewsKeywordsContractTest {
    @Test fun endpointAndNamedFieldsPreserveOrderAndUnicode() = runTest {
        val t=RecordingTransport(body(KEYWORD+","+KEYWORD.replace("POLICY","TERM")))
        val rows=NewsClient(t).keywords(42)
        assertEquals(listOf("/api/news/42/keywords"),t.paths)
        assertEquals(listOf(NewsKeywordCategory.POLICY,NewsKeywordCategory.TERM),rows.map{it.category})
        assertEquals("금리 😀",rows.first().keyword)
        assertEquals(listOf("뜻","맥락","확인"),rows.first().points)
        assertEquals("뜻",rows.first().definition);assertEquals("맥락",rows.first().context);assertEquals("확인",rows.first().watchPoint)
    }
    @Test fun emptyAndUnknownExtraFields() = runTest {
        val t=RecordingTransport(body(""));assertTrue(NewsClient(t).keywords(1).isEmpty())
        t.body=body(KEYWORD.dropLast(1)+",\"extra\":null}")
        assertEquals(1,NewsClient(t).keywords(1).size)
    }
    @Test fun malformedRequiredFieldsAreRejected() = runTest {
        val invalid=listOf("{}","null","[]","{\"keywords\":null}",body("null"),body(KEYWORD.replace("POLICY","UNKNOWN")),body(KEYWORD.replace("\"뜻\",\"맥락\",\"확인\"","\"뜻\"")),body(KEYWORD.replace("\"definition\":\"뜻\"","\"definition\":null")),body(KEYWORD.replace("\"context\":\"맥락\"","\"context\":3")),body(KEYWORD.replace("\"watchPoint\":\"확인\"","\"other\":\"확인\"")),body(KEYWORD.replace("\"keyword\":\"금리 😀\"","\"keyword\":false")))
        for(value in invalid) expectFailure<ResponseFormatException>{NewsClient(RecordingTransport(value)).keywords(1)}
    }
    @Test fun httpFailureAndCancellationAreNotConvertedToEmpty() = runTest {
        val t=RecordingTransport(body());val c=NewsClient(t)
        t.failure=ApiException(404,"NEWS_NOT_FOUND","private")
        assertEquals(404,expectFailure<ApiException>{c.keywords(1)}.status)
        t.failure=CancellationException("cancelled");expectFailure<CancellationException>{c.keywords(1)}
        t.failure=IOException("offline");expectFailure<IOException>{c.keywords(1)}
    }
    @Test fun detailAndKeywordsFailIndependentlyAndExplicitRetryRecovers() = runTest {
        val s=KeywordSource();s.answer={throw IOException("private-body")};val c=NewsController(s,this)
        try { c.setActive(true);c.openDetail(1);runCurrent()
            assertTrue(c.state.value.detail is LoadState.Ready)
            assertTrue(c.state.value.keywords is LoadState.Failed)
            assertFalse((c.state.value.keywords as LoadState.Failed).message.contains("private-body"))
            assertEquals(listOf(1L),s.calls)
            s.answer={emptyList()};c.retryKeywords();runCurrent()
            assertTrue((c.state.value.keywords as LoadState.Ready).value.isEmpty());assertEquals(2,s.calls.size)
        } finally {c.close()}
    }
    @Test fun lateResponseCannotCrossDetailOrBackBoundary() = runTest {
        val gate=CompletableDeferred<List<NewsKeyword>>();val s=KeywordSource()
        s.answer={id->if(id==1L)withContext(NonCancellable){gate.await()} else emptyList()}
        val c=NewsController(s,this)
        try {c.setActive(true);c.openDetail(1);runCurrent();c.openDetail(2);runCurrent()
            gate.complete(listOf(sampleKeyword()));runCurrent()
            assertEquals(2L,c.state.value.selectedId);assertTrue((c.state.value.keywords as LoadState.Ready).value.isEmpty())
            c.closeDetail();c.retryKeywords();runCurrent();assertEquals(LoadState.Idle,c.state.value.keywords);assertEquals(2,s.calls.size)
        } finally {gate.complete(emptyList());c.close()}
    }
    @Test fun inactiveAndCloseCancelAndPreventRequests() = runTest {
        var cancelled=false;val s=KeywordSource();s.answer={try{awaitCancellation()}finally{cancelled=true}}
        val c=NewsController(s,this);c.openDetail(1);runCurrent();assertTrue(s.calls.isEmpty())
        c.setActive(true);runCurrent();assertEquals(LoadState.Loading,c.state.value.keywords)
        c.setActive(false);runCurrent();assertTrue(cancelled);assertEquals(LoadState.Idle,c.state.value.keywords)
        s.answer={emptyList()};c.setActive(true);runCurrent();assertEquals(2,s.calls.size)
        c.close();c.retryKeywords();c.openDetail(2);c.setActive(true);runCurrent();assertEquals(2,s.calls.size)
    }
    @Test fun modeSwitchClearsKeywordsAndRejectsLateFailure() = runTest {
        val gate=CompletableDeferred<Unit>();val s=KeywordSource();s.answer={withContext(NonCancellable){gate.await();throw IOException("late")}}
        val c=NewsController(s,this)
        try {c.setActive(true);c.openDetail(1);runCurrent();c.selectToday(true);gate.complete(Unit);runCurrent()
            assertNull(c.state.value.selectedId);assertEquals(LoadState.Idle,c.state.value.keywords)
        } finally {gate.complete(Unit);c.close()}
    }
}
private fun sampleKeyword()=NewsKeyword(NewsKeywordCategory.POLICY,"금리",listOf("뜻","맥락","확인"),"뜻","맥락","확인")
private class KeywordSource:NewsSource {
    val calls=mutableListOf<Long>()
    var answer:suspend(Long)->List<NewsKeyword> = {listOf(sampleKeyword())}
    override suspend fun keywords(newsId:Long):List<NewsKeyword>{calls+=newsId;return answer(newsId)}
    override suspend fun list(category:NewsCategory?,page:Int,size:Int)=NewsPage(emptyList(),1,6,0,0,false)
    override suspend fun today()=list(null,1,9)
    override suspend fun detail(newsId:Long)=NewsDetail(newsId,"제목",NewsCategory.STOCK,"2026-11-04",listOf("본문"),null,null,emptyList())
}
