package org.daynomy.android

import android.content.Context
import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit
import okhttp3.mockwebserver.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Existing app + real loopback HTTP. No production server or DB. */
@RunWith(AndroidJUnit4::class)
class FeedbackScreenTest {
    @get:Rule val compose = createEmptyComposeRule()
    @Test fun publicAccountEntrySendsOnceAndShowsSuccess() {
        val writes = CopyOnWriteArrayList<RecordedRequest>()
        MockWebServer().use { server ->
            server.dispatcher = object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse = when (request.requestUrl?.encodedPath) {
                    "/api/auth/csrf" -> MockResponse().setBody("""{"headerName":"X-XSRF-TOKEN","token":"fixture-feedback"}""")
                        .addHeader("Set-Cookie", "XSRF-TOKEN=fixture-feedback; Path=/")
                    "/api/feedback" -> { writes += request; MockResponse().setResponseCode(204).setHeadersDelay(1, TimeUnit.SECONDS) }
                    "/api/users/me", "/api/auth/refresh" -> MockResponse().setResponseCode(401).setBody("""{"code":"UNAUTHORIZED"}""")
                    else -> MockResponse().setBody("[]")
                }
            }
            server.start()
            val context = ApplicationProvider.getApplicationContext<Context>()
            ActivityScenario.launch<MainActivity>(Intent(context, MainActivity::class.java)
                .putExtra("base_url", server.url("/").toString())).use {
                compose.onNodeWithTag("tab-account").performClick()
                compose.onNodeWithTag("account-feedback").performScrollTo().performClick()
                compose.onNodeWithTag("feedback-send").assertIsNotEnabled()
                compose.onNodeWithTag("feedback-content").performTextReplacement("  개선 의견 😀  ")
                compose.onNodeWithTag("feedback-send").performClick()
                compose.onNodeWithTag("feedback-send").assertIsNotEnabled()
                compose.waitUntil(10000) { compose.onAllNodesWithTag("feedback-success").fetchSemanticsNodes().isNotEmpty() }
                compose.onNodeWithTag("feedback-success").assertIsDisplayed()
                assertEquals(1, writes.size)
                assertEquals("fixture-feedback", writes.single().getHeader("X-XSRF-TOKEN"))
                assertTrue(writes.single().body.clone().readUtf8().contains("  개선 의견 😀  "))
                compose.onNodeWithTag("feedback-new").performClick()
                compose.onNodeWithTag("feedback-content").assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
                compose.onNodeWithTag("feedback-send").assertIsNotEnabled()
                compose.onNodeWithTag("feedback-close").performClick()
                compose.onNodeWithTag("account-feedback").assertIsDisplayed()
            }
        }
    }
}
