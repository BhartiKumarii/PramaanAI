package com.pramaanai.officer.data.docverify

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The on-phone MRZ check must use exactly the server's ICAO 9303 7-3-1 rule. */
class MrzCheckTest {
    private fun line2(number: String, dob: String, expiry: String, breakDob: Boolean = false): String {
        val num = number.padEnd(9, '<')
        val cd = MrzCheck.checkDigit(dob).let { if (breakDob) (it + 3) % 10 else it }
        return "$num${MrzCheck.checkDigit(num)}IND$dob${cd}F$expiry${MrzCheck.checkDigit(expiry)}" + "<".repeat(15) + "0"
    }

    @Test fun checkDigitMatchesIcaoExample() {
        // ICAO Doc 9303 worked example: document number L898902C3 -> check digit 6
        assertEquals(6, MrzCheck.checkDigit("L898902C3"))
        assertEquals(2, MrzCheck.checkDigit("740812"))
    }

    @Test fun validLinePasses() {
        val result = MrzCheck.validate(listOf("P<INDSHARMA<<ANANYA".padEnd(44, '<'), line2("Z1234567", "960412", "310509")))
        assertTrue(result!!.first)
    }

    @Test fun brokenDateOfBirthIsReportedAsPossibleMisread() {
        val result = MrzCheck.validate(listOf("P<INDX".padEnd(44, '<'), line2("Z1234567", "960412", "310509", breakDob = true)))
        assertFalse(result!!.first)
        assertTrue(result.second.contains("date of birth"))
        assertTrue(result.second.contains("server re-checks"))
    }

    @Test fun singleLineCannotBeChecked() {
        assertNull(MrzCheck.validate(listOf("P<INDX")))
    }
}
