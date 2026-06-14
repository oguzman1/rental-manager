import { Fragment, useEffect, useRef, useState } from 'react'
import Topbar from './Topbar'
import { PaymentBadge } from './Badge'
import { formatCLP, formatPeriodLabel, formatAmountInput, parseAmountInput } from './utils'

const API_BASE = 'http://127.0.0.1:8000'

const STATUS_ES = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagado' }

function todayLocal() {
  const now = new Date()
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('-')
}

function addOneMonth(period) {
  const [y, m] = period.split('-').map(Number)
  const nm = m === 12 ? 1 : m + 1
  const ny = m === 12 ? y + 1 : y
  return `${ny}-${String(nm).padStart(2, '0')}`
}

function isFullyPaid(payment) {
  if (!payment) return false
  return payment.status === 'paid'
}

// Returns the amount to prefill in "Agregar pago":
// - pending/null → expected_amount
// - partial → remaining balance (expected - paid)
// - paid → '' (no prefill; user can still type)
function getPrefillAmount(payment) {
  if (!payment) return ''
  if (payment.status === 'paid') return ''
  if (payment.status === 'partial') {
    const paid = payment.paid_amount ?? 0
    return String(Math.max(0, payment.expected_amount - paid))
  }
  return String(payment.expected_amount)
}

// Returns the next payable period using priority:
//   1. earliest partial  2. earliest pending  3. virtual next month (all paid)
function getNextPayablePeriod(payments, sortedPayments) {
  const asc = [...payments].sort((a, b) => a.period.localeCompare(b.period))
  const partial = asc.find(p => p.status === 'partial')
  if (partial) return { period: partial.period, payment: partial, isVirtual: false }
  const pending = asc.find(p => p.status === 'pending')
  if (pending) return { period: pending.period, payment: pending, isVirtual: false }
  if (sortedPayments.length > 0) {
    const [y, m] = sortedPayments[0].period.split('-').map(Number)
    const nextM = m === 12 ? 1 : m + 1
    const nextY = m === 12 ? y + 1 : y
    const period = `${nextY}-${String(nextM).padStart(2, '0')}`
    return { period, payment: null, isVirtual: true }
  }
  return { period: '', payment: null, isVirtual: false }
}

// Returns { ok: true, deductions: [...] } or { ok: false, error: string }.
// Fully empty rows (label+amount+note all blank) are silently dropped.
// Partially completed rows (one present, one missing) block the save.
function normalizeDeductions(rows) {
  const result = []
  for (const row of rows) {
    const labelBlank = !row.label.trim()
    const amountBlank = row.amount === ''
    const noteBlank = !row.note.trim()
    if (labelBlank && amountBlank && noteBlank) continue
    if (labelBlank || amountBlank) {
      return {
        ok: false,
        error: 'Completa concepto y monto en cada descuento, o elimina la fila vacía.',
      }
    }
    result.push({
      label: row.label.trim(),
      amount: parseAmountInput(row.amount),
      note: row.note.trim() || null,
    })
  }
  return { ok: true, deductions: result }
}

function PaymentsView({ contract, onBack, onPaymentMutation, targetPeriod, returnOnCancel = false }) {
  const [payments, setPayments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAll, setShowAll] = useState(false)

  // 'add' | 'edit' | null
  const [activeForm, setActiveForm] = useState(null)
  const [formError, setFormError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // "Agregar pago" form
  const [formPeriod, setFormPeriod] = useState('')
  const [formUseCustom, setFormUseCustom] = useState(false)
  const [formCustomPeriod, setFormCustomPeriod] = useState('')
  const [formAmount, setFormAmount] = useState('')
  const [formDate, setFormDate] = useState(todayLocal())
  const [formNote, setFormNote] = useState('')
  const [formDeductions, setFormDeductions] = useState([])
  const [formGgcc, setFormGgcc] = useState('')

  // Edit form
  const [editPayment, setEditPayment] = useState(null)
  const [editAmount, setEditAmount] = useState('')
  const [editDate, setEditDate] = useState('')
  const [editNote, setEditNote] = useState('')
  const [editDeductions, setEditDeductions] = useState([])
  const [editGgcc, setEditGgcc] = useState('')

  const [rentChanges, setRentChanges] = useState([])

  // Overpayment
  const [applyingOverpayment, setApplyingOverpayment] = useState(new Set())
  const [overpaymentError, setOverpaymentError] = useState(null)
  const [pendingOverpaymentId, setPendingOverpaymentId] = useState(null)
  // Keyed by payment.id → dismissed overpayment amount. Hides the prompt after "No abonar ahora"
  // until the payment is edited and the overpayment amount changes.
  const [dismissedOverpayments, setDismissedOverpayments] = useState({})
  // Pre-save overpayment draft: set when handleAdd/handleEdit detects excess before submitting.
  // Shape: { source, period, enteredAmount, expectedAmount, originPaidBefore, originPaidAfter,
  //          overpaymentAmount, formDate, formNote, paymentId, nextPeriod, nextPayment }
  const [pendingOverpaymentDraft, setPendingOverpaymentDraft] = useState(null)
  const [isRentChangeSaving, setIsRentChangeSaving] = useState(false)
  const resolverAutoOpenActiveRef = useRef(false)

  async function loadPayments() {
    try {
      const [pmtRes, rcRes] = await Promise.all([
        fetch(`${API_BASE}/contracts/${contract.id}/payments`),
        fetch(`${API_BASE}/contracts/${contract.id}/rent-changes`),
      ])
      if (!pmtRes.ok) throw new Error(`Error ${pmtRes.status}`)
      setPayments(await pmtRes.json())
      if (rcRes.ok) setRentChanges(await rcRes.json())
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    async function fetchData() {
      try {
        const [pmtRes, rcRes] = await Promise.all([
          fetch(`${API_BASE}/contracts/${contract.id}/payments`),
          fetch(`${API_BASE}/contracts/${contract.id}/rent-changes`),
        ])
        if (!pmtRes.ok) throw new Error(`Error ${pmtRes.status}`)
        const data = await pmtRes.json()
        if (!cancelled) {
          setPayments(data)
          if (rcRes.ok) setRentChanges(await rcRes.json())
          setIsLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
          setIsLoading(false)
        }
      }
    }
    fetchData()
    return () => { cancelled = true }
  }, [contract.id])

  const autoOpenedRef = useRef(false)
  useEffect(() => {
    if (isLoading || !targetPeriod || autoOpenedRef.current) return
    autoOpenedRef.current = true
    resolverAutoOpenActiveRef.current = returnOnCancel
    const p = payments.find(py => py.period === targetPeriod)
    if (p && p.status === 'partial') {
      openEdit(p)
    } else {
      openAdd()
    }
  }, [isLoading, targetPeriod]) // eslint-disable-line react-hooks/exhaustive-deps

  const sortedPayments = [...payments].sort((a, b) => b.period.localeCompare(a.period))
  const now = new Date()
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth() + 1
  const maxYear  = currentMonth === 12 ? currentYear + 1 : currentYear
  const maxMonth = currentMonth === 12 ? 1 : currentMonth + 1
  const maxPeriod = `${maxYear}-${String(maxMonth).padStart(2, '0')}`
  const minPeriod = `${currentYear}-01`
  const defaultVisiblePayments = sortedPayments.filter(
    p => p.period >= minPeriod && p.period <= maxPeriod
  )
  const hiddenCount = payments.length - defaultVisiblePayments.length
  const visiblePayments = showAll ? sortedPayments : defaultVisiblePayments

  // Next calendar month after the last known period — used as virtual "Próximo período" option
  const nextVirtualPeriod = (() => {
    if (sortedPayments.length === 0) return null
    const [y, m] = sortedPayments[0].period.split('-').map(Number)
    const nextM = m === 12 ? 1 : m + 1
    const nextY = m === 12 ? y + 1 : y
    return `${nextY}-${String(nextM).padStart(2, '0')}`
  })()

  function openAdd() {
    setFormDeductions([])
    setFormGgcc('')
    if (payments.length === 0) {
      setFormPeriod('')
      setFormUseCustom(true)
      setFormCustomPeriod(targetPeriod ?? todayLocal().slice(0, 7))
      setFormAmount(contract.current_rent != null ? formatAmountInput(contract.current_rent) : '')
      setFormDate(todayLocal())
      setFormNote('')
      setFormError(null)
      setActiveForm('add')
      return
    }

    if (targetPeriod) {
      const p = payments.find(py => py.period === targetPeriod) ?? null
      setFormPeriod(targetPeriod)
      setFormUseCustom(p === null && targetPeriod !== nextVirtualPeriod)
      setFormCustomPeriod(p === null && targetPeriod !== nextVirtualPeriod ? targetPeriod : '')
      setFormAmount(formatAmountInput(p ? getPrefillAmount(p) : contract.current_rent))
      setFormDate(todayLocal())
      setFormNote('')
      if (p) {
        setFormDeductions(
          (p.deductions ?? []).map(d => ({
            label: d.label,
            amount: d.amount ? formatAmountInput(String(d.amount)) : '',
            note: d.note ?? '',
          }))
        )
        const existingGgcc = (p.owner_expenses ?? []).find(e => isGgccExpense(e))
        setFormGgcc(existingGgcc ? formatAmountInput(String(existingGgcc.amount)) : '')
      }
      setFormError(null)
      setActiveForm('add')
      return
    }

    const { period, payment, isVirtual } = getNextPayablePeriod(payments, sortedPayments)
    setFormPeriod(period)
    setFormUseCustom(false)
    setFormCustomPeriod('')
    setFormAmount(formatAmountInput(isVirtual ? contract.current_rent : getPrefillAmount(payment)))
    setFormDate(todayLocal())
    setFormNote('')
    if (!isVirtual && payment) {
      setFormDeductions(
        (payment.deductions ?? []).map(d => ({
          label: d.label,
          amount: d.amount ? formatAmountInput(String(d.amount)) : '',
          note: d.note ?? '',
        }))
      )
      const existingGgcc = (payment.owner_expenses ?? []).find(e => isGgccExpense(e))
      setFormGgcc(existingGgcc ? formatAmountInput(String(existingGgcc.amount)) : '')
    }
    setFormError(null)
    setActiveForm('add')
  }

  function handlePeriodSelect(value) {
    if (value === '__custom__') {
      setFormUseCustom(true)
      return
    }
    setFormPeriod(value)
    setFormDeductions([])
    setFormGgcc('')
    const p = payments.find(py => py.period === value)
    if (p) {
      setFormAmount(formatAmountInput(getPrefillAmount(p)))
      setFormDate(p.paid_at ?? todayLocal())
      setFormDeductions(
        (p.deductions ?? []).map(d => ({
          label: d.label,
          amount: d.amount ? formatAmountInput(String(d.amount)) : '',
          note: d.note ?? '',
        }))
      )
      const existingGgcc = (p.owner_expenses ?? []).find(e => isGgccExpense(e))
      setFormGgcc(existingGgcc ? formatAmountInput(String(existingGgcc.amount)) : '')
    } else {
      // Virtual period not yet created — default to expected monthly rent
      setFormAmount(formatAmountInput(contract.current_rent))
      setFormDate(todayLocal())
    }
  }

  function openEdit(payment) {
    setEditPayment(payment)
    setEditAmount(formatAmountInput(payment.paid_amount ?? payment.expected_amount))
    setEditDate(payment.paid_at ?? todayLocal())
    setEditNote(payment.comment ?? '')
    setEditDeductions(
      (payment.deductions ?? []).map(d => ({
        label: d.label,
        amount: d.amount ? formatAmountInput(String(d.amount)) : '',
        note: d.note ?? '',
      }))
    )
    const existingGgcc = (payment.owner_expenses ?? []).find(e => isGgccExpense(e))
    setEditGgcc(existingGgcc ? formatAmountInput(String(existingGgcc.amount)) : '')
    setFormError(null)
    setActiveForm('edit')
  }

  function cancelForm() {
    const shouldReturn = resolverAutoOpenActiveRef.current
    resolverAutoOpenActiveRef.current = false
    setPendingOverpaymentDraft(null)
    setActiveForm(null)
    setFormError(null)
    if (shouldReturn) onBack()
  }

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget && !pendingOverpaymentDraft) cancelForm()
  }

  async function handleAdd(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    setOverpaymentError(null)
    const period = formUseCustom ? formCustomPeriod : formPeriod
    const amount = parseAmountInput(formAmount)
    const existing = payments.find(p => p.period === period)

    // Validate deductions before the overpayment check so partial rows are caught
    // immediately, never reach the draft, and never get submitted.
    const dedResult = normalizeDeductions(formDeductions)
    if (!dedResult.ok) {
      setFormError(dedResult.error)
      setIsSubmitting(false)
      return
    }
    const normalizedDeds = dedResult.deductions

    const expectedAmount = existing ? existing.expected_amount : (contract.current_rent ?? 0)
    const alreadyPaid = existing ? (existing.paid_amount ?? 0) : 0
    const originPaidAfter = alreadyPaid + amount
    const overpaymentAmount = Math.max(0, originPaidAfter - expectedAmount)
    if (overpaymentAmount > 0) {
      const nextPeriod = addOneMonth(period)
      const nextPayment = payments.find(p => p.period === nextPeriod) ?? null
      setPendingOverpaymentDraft({
        source: 'add',
        period,
        enteredAmount: amount,
        expectedAmount,
        originPaidBefore: alreadyPaid,
        originPaidAfter,
        overpaymentAmount,
        formDate,
        formNote,
        formDeductions: normalizedDeds,
        formOwnerExpenses: mergeGgccOwnerExpense([], formGgcc),
        paymentId: existing?.id ?? null,
        nextPeriod,
        nextPayment,
      })
      setIsSubmitting(false)
      return
    }
    try {
      if (existing) {
        const res = await fetch(`${API_BASE}/payments/${existing.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paid_amount: (existing.paid_amount ?? 0) + amount,
            paid_at: formDate,
            comment: formNote !== '' ? formNote : null,
            deductions: normalizedDeds,
            owner_expenses: mergeGgccOwnerExpense(existing.owner_expenses, formGgcc),
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
      } else {
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            paid_amount: amount || null,
            paid_at: formDate || null,
            comment: formNote || null,
            deductions: normalizedDeds,
            owner_expenses: mergeGgccOwnerExpense([], formGgcc),
          }),
        })
        if (res.status === 409) {
          setFormError(`Ya existe un pago para el período ${period}.`)
          return
        }
        if (!res.ok) throw new Error(`Error ${res.status}`)
      }
      resolverAutoOpenActiveRef.current = false
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleEdit(e) {
    e.preventDefault()
    setIsSubmitting(true)
    setFormError(null)
    const dedResult = normalizeDeductions(editDeductions)
    if (!dedResult.ok) {
      setFormError(dedResult.error)
      setIsSubmitting(false)
      return
    }
    const newTotal = parseAmountInput(editAmount)
    const originPaidBefore = editPayment.paid_amount ?? 0
    const expectedAmount = editPayment.expected_amount
    const overpaymentAmount = Math.max(0, newTotal - expectedAmount)
    if (overpaymentAmount > 0) {
      const period = editPayment.period
      const nextPeriod = addOneMonth(period)
      const nextPayment = payments.find(p => p.period === nextPeriod) ?? null
      setPendingOverpaymentDraft({
        source: 'edit',
        period,
        enteredAmount: newTotal,
        expectedAmount,
        originPaidBefore,
        originPaidAfter: newTotal,
        overpaymentAmount,
        formDate: editDate,
        formNote: editNote,
        paymentId: editPayment.id,
        nextPeriod,
        nextPayment,
      })
      setIsSubmitting(false)
      return
    }
    try {
      const body = {}
      if (editAmount !== '') body.paid_amount = newTotal
      if (editDate !== '') body.paid_at = editDate
      body.comment = editNote !== '' ? editNote : null
      body.deductions = dedResult.deductions
      body.owner_expenses = mergeGgccOwnerExpense(editPayment.owner_expenses, editGgcc)
      const res = await fetch(`${API_BASE}/payments/${editPayment.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        throw new Error(errData?.detail ?? `Error ${res.status}`)
      }
      resolverAutoOpenActiveRef.current = false
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDelete(payment) {
    if (!window.confirm(`¿Eliminar el pago de ${payment.period}?`)) return
    try {
      const res = await fetch(`${API_BASE}/payments/${payment.id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleApplyOverpayment(payment) {
    setPendingOverpaymentId(null)
    setApplyingOverpayment(prev => new Set([...prev, payment.id]))
    setOverpaymentError(null)
    try {
      const res = await fetch(`${API_BASE}/payments/${payment.id}/apply-overpayment`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      setDismissedOverpayments(prev => {
        const next = { ...prev }
        delete next[payment.id]
        return next
      })
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setOverpaymentError(err.message)
    } finally {
      setApplyingOverpayment(prev => {
        const next = new Set(prev)
        next.delete(payment.id)
        return next
      })
    }
  }

  // Saves the payment from pendingOverpaymentDraft.
  // applyAfter=true: also calls apply-overpayment (Case A/B).
  // applyAfter=false: saves only, no transfer (Case C — next period fully paid).
  async function saveFromDraft(applyAfter) {
    if (!pendingOverpaymentDraft) return
    const { period, paymentId, originPaidAfter, formDate, formNote, formDeductions: draftDeductions, formOwnerExpenses: draftOwnerExpenses } = pendingOverpaymentDraft
    setIsSubmitting(true)
    setFormError(null)
    setOverpaymentError(null)
    try {
      let resolvedId = paymentId
      if (paymentId != null) {
        // PATCH: add-to-existing (originPaidAfter = alreadyPaid + entered)
        //        or edit (originPaidAfter = entered, replaces rather than adds)
        const res = await fetch(`${API_BASE}/payments/${paymentId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paid_amount: originPaidAfter,
            ...(formDate ? { paid_at: formDate } : {}),
            comment: formNote !== '' ? formNote : null,
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
      } else {
        // POST: new period (add flow only, paymentId is null)
        const res = await fetch(`${API_BASE}/contracts/${contract.id}/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            period,
            paid_amount: originPaidAfter || null,
            paid_at: formDate || null,
            comment: formNote || null,
            deductions: draftDeductions ?? [],
            owner_expenses: draftOwnerExpenses ?? [],
          }),
        })
        if (!res.ok) throw new Error(`Error ${res.status}`)
        const data = await res.json()
        resolvedId = data.id
      }
      if (applyAfter) {
        const applyRes = await fetch(
          `${API_BASE}/payments/${resolvedId}/apply-overpayment`,
          { method: 'POST' }
        )
        if (!applyRes.ok) {
          // Payment already persisted — do not retry. Reload and show row-level error.
          setPendingOverpaymentDraft(null)
          setActiveForm(null)
          await loadPayments()
          await onPaymentMutation?.()
          setOverpaymentError('El pago se guardó, pero no se pudo abonar el excedente. Intenta nuevamente desde la fila.')
          return
        }
      }
      setPendingOverpaymentDraft(null)
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Registers the entered amount as a new rent and saves the payment at the new expected amount.
  // Uses the atomic backend endpoint so rent_change and payment are committed in one transaction.
  async function saveAsRentChange() {
    if (!pendingOverpaymentDraft) return
    const {
      source,
      period,
      enteredAmount,
      originPaidAfter,
      formDate,
      formNote,
      formDeductions: draftDeductions,
      formOwnerExpenses: draftOwnerExpenses,
      paymentId,
    } = pendingOverpaymentDraft

    let deductions = []
    let owner_expenses = []
    if (source === 'add' && draftDeductions) {
      deductions = draftDeductions
      owner_expenses = draftOwnerExpenses ?? []
    } else if (source === 'edit') {
      const dedResult = normalizeDeductions(editDeductions)
      if (dedResult.ok) deductions = dedResult.deductions
      owner_expenses = mergeGgccOwnerExpense(editPayment?.owner_expenses, editGgcc)
    }

    const body = {
      period,
      new_rent_amount: enteredAmount,
      paid_amount: originPaidAfter,
      comment: formNote !== '' ? formNote : null,
      payment_id: paymentId ?? null,
      deductions,
      owner_expenses,
    }
    if (formDate) body.paid_at = formDate

    setIsRentChangeSaving(true)
    setFormError(null)
    try {
      const res = await fetch(`${API_BASE}/contracts/${contract.id}/rent-change-payment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        const detail = errData?.detail ?? ''
        const isChrono = detail.includes('strictly after') || detail.includes('reajuste posterior')
        throw new Error(
          isChrono
            ? 'No se puede registrar este reajuste porque ya existe un reajuste posterior. Usa otra opción o revisa Reajustes.'
            : detail || `Error al registrar reajuste: ${res.status}`
        )
      }

      setPendingOverpaymentDraft(null)
      resolverAutoOpenActiveRef.current = false
      setActiveForm(null)
      await loadPayments()
      await onPaymentMutation?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setIsRentChangeSaving(false)
    }
  }

  const periodOptions = [...payments].sort((a, b) => a.period.localeCompare(b.period))
  const addFormTargetPeriod = formUseCustom ? formCustomPeriod : formPeriod
  const addFormIsNewRow = !payments.some(p => p.period === addFormTargetPeriod)

  const addFormExistingPayment = payments.find(p => p.period === addFormTargetPeriod) ?? null
  const addTotalDeductions = formDeductions.reduce(
    (s, d) => s + (d.amount !== '' ? parseAmountInput(d.amount) : 0), 0
  )
  const editTotalDeductions = editDeductions.reduce(
    (s, d) => s + (d.amount !== '' ? parseAmountInput(d.amount) : 0), 0
  )

  // Broker helper computed values
  const brokerEnabled = contract.broker_fee_enabled === true
  const usualBrokerFee = contract.usual_broker_fee ?? 0

  const addPaidAmt = formAmount !== '' ? parseAmountInput(formAmount) : 0
  const addExpected = addFormExistingPayment?.expected_amount ?? contract.current_rent ?? 0
  const addExistingPaid = addFormExistingPayment ? (addFormExistingPayment.paid_amount ?? 0) : 0
  const addCumulativePaid = addExistingPaid + addPaidAmt
  const addBrokerDedAmt = (() => {
    const b = formDeductions.find(d => d.label === 'Corredora')
    return b && b.amount !== '' ? parseAmountInput(b.amount) : 0
  })()
  const addNonBrokerDeds = addTotalDeductions - addBrokerDedAmt
  const addBrokerDiff = addExpected - addCumulativePaid - addNonBrokerDeds
  const addRecognized = addCumulativePaid + addTotalDeductions
  const addMissing = Math.max(0, addExpected - addRecognized)

  const editPaidAmt = editAmount !== '' ? parseAmountInput(editAmount) : 0
  const editExpected = editPayment?.expected_amount ?? 0
  const editBrokerDedAmt = (() => {
    const b = editDeductions.find(d => d.label === 'Corredora')
    return b && b.amount !== '' ? parseAmountInput(b.amount) : 0
  })()
  const editNonBrokerDeds = editTotalDeductions - editBrokerDedAmt
  const editBrokerDiff = editExpected - editPaidAmt - editNonBrokerDeds
  const editRecognized = editPaidAmt + editTotalDeductions
  const editMissing = Math.max(0, editExpected - editRecognized)

  const ggccEnabled = contract.owner_pays_ggcc === true

  function sumOwnerExpenses(expenses) {
    return (expenses ?? []).reduce((s, e) => s + (e.amount ?? 0), 0)
  }

  const addMergedOwnerExpenses = mergeGgccOwnerExpense(addFormExistingPayment?.owner_expenses, formGgcc)
  const addOwnerExpenseTotal = sumOwnerExpenses(addMergedOwnerExpenses)
  const addNetOwner = addCumulativePaid - addOwnerExpenseTotal

  const editMergedOwnerExpenses = mergeGgccOwnerExpense(editPayment?.owner_expenses, editGgcc)
  const editOwnerExpenseTotal = sumOwnerExpenses(editMergedOwnerExpenses)
  const editNetOwner = editPaidAmt - editOwnerExpenseTotal

  function isGgccExpense(expense) {
    const label = (expense.label ?? '').toLowerCase()
    return label.includes('gastos comunes') || label.includes('gg.cc')
  }

  function mergeGgccOwnerExpense(existingOwnerExpenses, ggccStr) {
    const others = (existingOwnerExpenses ?? []).filter(e => !isGgccExpense(e))
    const amt = ggccStr !== '' ? parseAmountInput(ggccStr) : 0
    if (amt <= 0) return others
    return [...others, { label: 'Gastos comunes', amount: amt, note: null }]
  }

  function imputarCorredora(diff, deductions, setDeductions) {
    const toImpute = Math.min(Math.max(0, diff), usualBrokerFee)
    if (toImpute <= 0) return
    const amtStr = formatAmountInput(String(toImpute))
    const idx = deductions.findIndex(d => d.label === 'Corredora')
    if (idx >= 0) {
      setDeductions(prev => prev.map((r, i) => i === idx ? { ...r, amount: amtStr } : r))
    } else {
      setDeductions(prev => [...prev, { label: 'Corredora', amount: amtStr, note: '' }])
    }
  }

  function statusPreview(recognized, expected) {
    if (recognized >= expected) return 'Pagado'
    if (recognized > 0) return 'Parcial'
    return 'Pendiente'
  }

  // Build the inline confirmation panel JSX once, shared by add and edit forms.
  let overpaymentPanel = null
  if (pendingOverpaymentDraft) {
    const {
      source,
      period,
      enteredAmount,
      expectedAmount,
      originPaidBefore,
      originPaidAfter,
      overpaymentAmount,
      nextPeriod,
      nextPayment,
    } = pendingOverpaymentDraft

    const latestRcEffectiveFrom = rentChanges.length > 0 ? rentChanges[0].effective_from : null
    const candidateEffectiveFrom = period + '-01'
    const rentChangeAllowed = !latestRcEffectiveFrom || candidateEffectiveFrom > latestRcEffectiveFrom

    const fullyPaidBlocked = isFullyPaid(nextPayment)
    const nextRemainingCapacity = nextPayment == null
      ? (contract.current_rent ?? 0)
      : Math.max(0, (nextPayment.expected_amount ?? 0) - (nextPayment.paid_amount ?? 0))
    const overflowBlocked = overpaymentAmount > nextRemainingCapacity
    const nextBlocked = fullyPaidBlocked || overflowBlocked

    let originLine
    if (source === 'edit') {
      originLine = (
        <>
          Monto actualizado: <strong>{formatCLP(originPaidAfter)}</strong>
          {' '}(antes: {formatCLP(originPaidBefore)})
          {' · '}Esperado: {formatCLP(expectedAmount)}
          {' · '}Excedente: <strong>{formatCLP(overpaymentAmount)}</strong>
        </>
      )
    } else if (originPaidBefore > 0) {
      originLine = (
        <>
          Ya pagado: {formatCLP(originPaidBefore)}
          {' + '}Nuevo abono: {formatCLP(enteredAmount)}
          {' = '}Total: <strong>{formatCLP(originPaidAfter)}</strong>
          {' · '}Esperado: {formatCLP(expectedAmount)}
          {' · '}Excedente: <strong>{formatCLP(overpaymentAmount)}</strong>
        </>
      )
    } else {
      originLine = (
        <>
          Registrado: <strong>{formatCLP(originPaidAfter)}</strong>
          {' · '}Esperado: {formatCLP(expectedAmount)}
          {' · '}Excedente: <strong>{formatCLP(overpaymentAmount)}</strong>
        </>
      )
    }

    let destLine
    if (fullyPaidBlocked) {
      destLine = (
        <>
          ⚠ <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— ya está totalmente pagado.
        </>
      )
    } else if (nextPayment == null) {
      destLine = (
        <>
          <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— aún no existe. Se creará al aplicar el excedente.
        </>
      )
    } else {
      const currentPaid = nextPayment.paid_amount ?? 0
      const afterApply = currentPaid + overpaymentAmount
      const nextExpected = nextPayment.expected_amount
      destLine = currentPaid === 0 ? (
        <>
          <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— pendiente, sin pago registrado.
          {' '}Después de aplicar: <strong>{formatCLP(overpaymentAmount)}</strong> de {formatCLP(nextExpected)}.
        </>
      ) : (
        <>
          <strong>Período de destino: {formatPeriodLabel(nextPeriod)}</strong>
          {' '}— parcial: {formatCLP(currentPaid)} de {formatCLP(nextExpected)}.
          {' '}Después de aplicar: <strong>{formatCLP(afterApply)}</strong> de {formatCLP(nextExpected)}.
        </>
      )
    }

    overpaymentPanel = (
      <div className="payment-overpayment-inline">
        <p className="payment-overpayment-heading">
          ¿Cómo quieres tratar la diferencia?
        </p>
        <p className="payment-overpayment-confirm-text">
          El monto ingresado supera lo esperado para este período.
        </p>
        <p className="payment-overpayment-confirm-text">
          <strong>Período de origen: {formatPeriodLabel(period)}</strong>
          <br />
          {originLine}
        </p>
        <p className="payment-overpayment-confirm-text">
          {destLine}
        </p>
        <p className="payment-overpayment-confirm-text">
          {fullyPaidBlocked
            ? 'El período de destino ya está totalmente pagado. Si guardas sin abonar excedente, el sobrepago quedará registrado en el período de origen.'
            : overflowBlocked
              ? 'El excedente supera lo que necesita el período de destino. La asignación automática en múltiples períodos aún no está disponible. Si guardas sin abonar excedente, el sobrepago quedará registrado en el período de origen.'
              : `Si guardas y abonas el excedente, se abonarán ${formatCLP(overpaymentAmount)} a ${formatPeriodLabel(nextPeriod)}.`
          }
        </p>
        <p className="payment-overpayment-confirm-text">
          {rentChangeAllowed
            ? `Actualizaría el arriendo a ${formatCLP(enteredAmount)} desde ${formatPeriodLabel(period)}.`
            : `No se puede registrar un reajuste desde ${formatPeriodLabel(period)} porque ya existe un reajuste posterior.`}
        </p>
        <div className="payment-form-actions">
          {!nextBlocked && (
            <button
              type="button"
              className="btn-primary"
              onClick={() => saveFromDraft(true)}
              disabled={isSubmitting || isRentChangeSaving}
            >
              {isSubmitting ? 'Guardando…' : 'Pasar diferencia al siguiente mes'}
            </button>
          )}
          {nextBlocked && (
            <button
              type="button"
              className="btn-warn-sm"
              onClick={() => saveFromDraft(false)}
              disabled={isSubmitting || isRentChangeSaving}
            >
              {isSubmitting ? 'Guardando…' : 'Guardar sin abonar excedente'}
            </button>
          )}
          {rentChangeAllowed && (
            <button
              type="button"
              className="btn-secondary"
              onClick={saveAsRentChange}
              disabled={isSubmitting || isRentChangeSaving}
            >
              {isRentChangeSaving ? 'Guardando…' : 'Actualizar arriendo'}
            </button>
          )}
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setPendingOverpaymentDraft(null)}
            disabled={isSubmitting || isRentChangeSaving}
          >
            Editar monto
          </button>
        </div>
      </div>
    )
  }

  return (
    <>
      <Topbar
        title={`Pagos — ${contract.property_label}`}
        breadcrumb={['Contratos', contract.property_label]}
        actions={
          <button className="btn-secondary" onClick={onBack}>
            ← Volver
          </button>
        }
      />
      <div className="page-body">
        <div className="payment-info-line">
          <span>{contract.tenant_name}</span>
          <span className="payment-info-sep">·</span>
          <span>Esperado: {formatCLP(contract.current_rent)}</span>
          <span className="payment-info-sep">·</span>
          <span>Día de pago: {contract.payment_day}</span>
        </div>

        {isLoading && <div className="app-loading">Cargando pagos…</div>}
        {!isLoading && error && <div className="app-error">Error al cargar: {error}</div>}

        {/* Toolbar: main action + period toggle — toggle is always independent of activeForm */}
        {!isLoading && !error && (
          <div className="payment-table-toolbar">
            <button className="btn-primary" onClick={openAdd}>
              + Agregar pago
            </button>
            {hiddenCount > 0 && (
              !showAll ? (
                <button className="btn-link-secondary" onClick={() => setShowAll(true)}>
                  Mostrar más períodos ({hiddenCount})
                </button>
              ) : (
                <button className="btn-link-secondary" onClick={() => setShowAll(false)}>
                  Mostrar menos
                </button>
              )
            )}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && payments.length === 0 && (
          <div className="payment-empty">
            <p className="payment-empty-text">Sin períodos generados para este contrato.</p>
          </div>
        )}

        {/* Period table */}
        {!isLoading && !error && visiblePayments.length > 0 && (
          <div className="table-scroll">
            <div className="table-wrapper">
              <table className="dashboard-table">
                <thead>
                  <tr>
                    <th className="th">Período</th>
                    <th className="th">Vencimiento</th>
                    <th className="th th-right">Esperado</th>
                    <th className="th th-right">Pagado</th>
                    <th className="th">Fecha pago</th>
                    <th className="th">Estado</th>
                    <th className="th">Nota</th>
                    <th className="th th-actions">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePayments.map(p => {
                    const rowNextPeriod = addOneMonth(p.period)
                    const rowNextPayment = payments.find(q => q.period === rowNextPeriod) ?? null
                    const rowIsBlocked = isFullyPaid(rowNextPayment)
                    const rowNextRemainingCapacity = rowNextPayment == null
                      ? (contract.current_rent ?? 0)
                      : Math.max(0, (rowNextPayment.expected_amount ?? 0) - (rowNextPayment.paid_amount ?? 0))
                    const rowOverflowBlocked = p.overpayment > rowNextRemainingCapacity
                    return (
                      <Fragment key={p.id}>
                        <tr className="table-row-static">
                          <td className="td td-mono">{formatPeriodLabel(p.period)}</td>
                          <td className="td td-mono td-muted">{p.due_date}</td>
                          <td className="td td-right td-mono">{formatCLP(p.expected_amount)}</td>
                          <td className="td td-right td-mono">
                            {p.paid_amount != null
                              ? formatCLP(p.paid_amount)
                              : <span className="text-muted">—</span>}
                            {p.deductions && p.deductions.length > 0 && (
                              <span className="text-muted" style={{ fontSize: '0.75em', display: 'block' }}>
                                Neto dueño: {formatCLP(p.net_owner_amount)}
                              </span>
                            )}
                          </td>
                          <td className="td td-mono td-muted">
                            {p.paid_at ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td">
                            <PaymentBadge status={p.status} />
                          </td>
                          <td className="td td-muted">
                            {p.comment ?? <span className="text-muted">—</span>}
                          </td>
                          <td className="td td-actions">
                            <button className="btn-payments" onClick={() => openEdit(p)}>
                              Editar
                            </button>
                            {' '}
                            <button className="btn-payments-danger" onClick={() => handleDelete(p)}>
                              Eliminar
                            </button>
                          </td>
                        </tr>
                        {p.overpayment > 0 && dismissedOverpayments[p.id] !== p.overpayment && (
                          <tr className="overpayment-row">
                            <td colSpan={8} className="overpayment-cell">
                              <span className="overpayment-label">
                                Sobrepago: {formatCLP(p.overpayment)}
                              </span>
                              {rowIsBlocked ? (
                                <>
                                  <span className="overpayment-confirm-text">
                                    El período siguiente ({formatPeriodLabel(rowNextPeriod)}) ya está totalmente pagado. Aplicar este excedente generaría otro sobrepago. Revisa manualmente.
                                  </span>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => setDismissedOverpayments(prev => ({ ...prev, [p.id]: p.overpayment }))}
                                  >
                                    No abonar ahora
                                  </button>
                                </>
                              ) : rowOverflowBlocked ? (
                                <>
                                  <span className="overpayment-confirm-text">
                                    El excedente supera lo que necesita el período siguiente. Abonarlo ahora generaría otro sobrepago.
                                  </span>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => setDismissedOverpayments(prev => ({ ...prev, [p.id]: p.overpayment }))}
                                  >
                                    No abonar ahora
                                  </button>
                                </>
                              ) : pendingOverpaymentId === p.id ? (
                                <>
                                  <span className="overpayment-confirm-text">
                                    ¿Abonar este sobrepago al próximo período?
                                  </span>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => handleApplyOverpayment(p)}
                                    disabled={applyingOverpayment.has(p.id)}
                                  >
                                    {applyingOverpayment.has(p.id) ? 'Aplicando…' : 'Confirmar'}
                                  </button>
                                  <button
                                    className="btn-warn-sm"
                                    onClick={() => {
                                      setPendingOverpaymentId(null)
                                      setDismissedOverpayments(prev => ({ ...prev, [p.id]: p.overpayment }))
                                    }}
                                  >
                                    No abonar ahora
                                  </button>
                                </>
                              ) : (
                                <button
                                  className="btn-warn-sm"
                                  onClick={() => setPendingOverpaymentId(p.id)}
                                  disabled={applyingOverpayment.has(p.id)}
                                >
                                  {applyingOverpayment.has(p.id) ? 'Aplicando…' : 'Abonar al próximo periodo'}
                                </button>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
              <div className="table-footer">
                <span>
                  {visiblePayments.length} período{visiblePayments.length !== 1 ? 's' : ''}
                  {!showAll && hiddenCount > 0 && ` · ${hiddenCount} ocultos`}
                </span>
              </div>
            </div>
          </div>
        )}

        {overpaymentError && (
          <div className="payment-form-error" style={{ padding: '8px 20px' }}>
            {overpaymentError}
          </div>
        )}
      </div>

      {/* Payment modal */}
      {activeForm !== null && (
        <div className="payment-modal-overlay" onClick={handleOverlayClick}>
          <div className="payment-modal-panel">
            <div className="payment-modal-header">
              <span className="payment-modal-title">
                {activeForm === 'add'
                  ? `Agregar pago — ${contract.property_label}`
                  : `Editar pago — ${contract.property_label}`}
              </span>
              <button className="payment-modal-close" type="button" onClick={cancelForm}>×</button>
            </div>
            <div className="payment-modal-body">
              {/* Add form */}
              {activeForm === 'add' && (
                <form className="payment-form" onSubmit={handleAdd}>
                  <div className="payment-form-row">
                    {!formUseCustom ? (
                      <label className="payment-form-label">
                        Período
                        <select
                          className="payment-form-input"
                          value={formPeriod}
                          onChange={e => handlePeriodSelect(e.target.value)}
                          disabled={!!pendingOverpaymentDraft}
                        >
                          {periodOptions.map(p => (
                            <option key={p.period} value={p.period}>
                              {formatPeriodLabel(p.period)} — {STATUS_ES[p.status] ?? p.status}
                            </option>
                          ))}
                          {nextVirtualPeriod && !payments.some(p => p.period === nextVirtualPeriod) && (
                            <option value={nextVirtualPeriod}>
                              Próximo período — {formatPeriodLabel(nextVirtualPeriod)}
                            </option>
                          )}
                          <option value="__custom__">Otro período…</option>
                        </select>
                      </label>
                    ) : (
                      <label className="payment-form-label">
                        Período
                        <input
                          className="payment-form-input"
                          type="text"
                          value={formCustomPeriod}
                          onChange={e => setFormCustomPeriod(e.target.value)}
                          placeholder="ej. 2025-04"
                          required
                          disabled={!!pendingOverpaymentDraft}
                        />
                        {payments.length > 0 && !pendingOverpaymentDraft && (
                          <button
                            type="button"
                            className="btn-link-secondary"
                            onClick={() => setFormUseCustom(false)}
                          >
                            ← Seleccionar de lista
                          </button>
                        )}
                      </label>
                    )}
                    <label className="payment-form-label">
                      Arriendo cobrado / total ingresos
                      <input
                        className="payment-form-input"
                        type="text"
                        inputMode="numeric"
                        value={formAmount}
                        onChange={e => setFormAmount(formatAmountInput(e.target.value))}
                        placeholder={`ej. ${formatAmountInput(contract.current_rent)}`}
                        required
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <label className="payment-form-label">
                      Fecha pago
                      <input
                        className="payment-form-input"
                        type="date"
                        value={formDate}
                        onChange={e => setFormDate(e.target.value)}
                        required
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <label className="payment-form-label">
                      Nota
                      <input
                        className="payment-form-input"
                        type="text"
                        value={formNote}
                        onChange={e => setFormNote(e.target.value)}
                        placeholder="opcional"
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <div className="deductions-section">
                        <span className="deductions-section-label">Descuentos / liquidación al dueño</span>
                        {formDeductions.map((row, i) => (
                          <div key={i} className="deduction-row">
                            <input
                              className="payment-form-input deduction-input-label"
                              type="text"
                              value={row.label}
                              onChange={e => setFormDeductions(prev => prev.map((r, j) => j === i ? { ...r, label: e.target.value } : r))}
                              placeholder="Concepto"
                              disabled={!!pendingOverpaymentDraft}
                            />
                            <input
                              className="payment-form-input deduction-input-amount"
                              type="text"
                              inputMode="numeric"
                              value={row.amount}
                              onChange={e => setFormDeductions(prev => prev.map((r, j) => j === i ? { ...r, amount: formatAmountInput(e.target.value) } : r))}
                              placeholder="0"
                              disabled={!!pendingOverpaymentDraft}
                            />
                            <input
                              className="payment-form-input deduction-input-note"
                              type="text"
                              value={row.note}
                              onChange={e => setFormDeductions(prev => prev.map((r, j) => j === i ? { ...r, note: e.target.value } : r))}
                              placeholder="Nota opcional"
                              disabled={!!pendingOverpaymentDraft}
                            />
                            {!pendingOverpaymentDraft && (
                              <button
                                type="button"
                                className="btn-link-secondary"
                                onClick={() => setFormDeductions(prev => prev.filter((_, j) => j !== i))}
                              >
                                ×
                              </button>
                            )}
                          </div>
                        ))}
                        {!pendingOverpaymentDraft && (
                          <button
                            type="button"
                            className="btn-link-secondary"
                            onClick={() => setFormDeductions(prev => [...prev, { label: '', amount: '', note: '' }])}
                          >
                            + Agregar descuento
                          </button>
                        )}
                        {brokerEnabled && !pendingOverpaymentDraft && (
                          <div className="broker-helper">
                            <span className="broker-helper-label">Corredora</span>
                            <span className="broker-helper-diff">
                              Diferencia: <strong>{formatCLP(addBrokerDiff)}</strong>
                              {addBrokerDiff > usualBrokerFee && (
                                <span className="text-muted">
                                  {' · '}Corredora: {formatCLP(usualBrokerFee)}
                                  {' · '}Pendiente: <strong style={{ color: 'var(--warn, #b45309)' }}>{formatCLP(addBrokerDiff - usualBrokerFee)}</strong>
                                </span>
                              )}
                            </span>
                            {addBrokerDiff > 0 && usualBrokerFee > 0 && (
                              <button
                                type="button"
                                className="btn-link-secondary"
                                onClick={() => imputarCorredora(addBrokerDiff, formDeductions, setFormDeductions)}
                              >
                                Imputar diferencia a corredora
                              </button>
                            )}
                          </div>
                        )}
                        <span className="text-muted" style={{ fontSize: '0.85em' }}>
                          Esperado: {formatCLP(addExpected)}
                          {' · '}Pagado: {formatCLP(addPaidAmt)}
                          {addTotalDeductions > 0 && <>{' · '}Descuentos: {formatCLP(addTotalDeductions)}</>}
                          {' · '}Reconocido: <strong style={{ color: 'var(--ink)' }}>{formatCLP(addRecognized)}</strong>
                          {addMissing > 0 && (
                            <>{' · '}Pendiente: <strong style={{ color: 'var(--warn, #b45309)' }}>{formatCLP(addMissing)}</strong></>
                          )}
                          {' · '}Estado: <strong style={{ color: 'var(--ink)' }}>{statusPreview(addRecognized, addExpected)}</strong>
                          {ggccEnabled && addOwnerExpenseTotal > 0 && (
                            <>{' · '}Gasto dueño: {formatCLP(addOwnerExpenseTotal)}{' · '}Neto dueño: <strong style={{ color: 'var(--ink)' }}>{formatCLP(addNetOwner)}</strong></>
                          )}
                        </span>
                      </div>
                    {ggccEnabled && !pendingOverpaymentDraft && (
                      <div className="ggcc-section">
                        <span className="ggcc-section-label">GG.CC. — Gasto dueño</span>
                        <input
                          className="payment-form-input"
                          type="text"
                          inputMode="numeric"
                          value={formGgcc}
                          onChange={e => setFormGgcc(formatAmountInput(e.target.value))}
                          placeholder="Monto GG.CC."
                        />
                        {formGgcc === '' && (
                          <span className="text-muted" style={{ fontSize: '0.85em' }}>
                            Puedes registrar los GG.CC. después.
                          </span>
                        )}
                      </div>
                    )}
                    {!pendingOverpaymentDraft && (
                      <div className="payment-form-actions">
                        <button className="btn-primary" type="submit" disabled={isSubmitting}>
                          {isSubmitting ? 'Guardando…' : 'Guardar'}
                        </button>
                        <button className="btn-secondary" type="button" onClick={cancelForm}>
                          Cancelar
                        </button>
                      </div>
                    )}
                  </div>
                  {pendingOverpaymentDraft?.source === 'add' && overpaymentPanel}
                  {formError && <div className="payment-form-error">{formError}</div>}
                </form>
              )}

              {/* Edit form */}
              {activeForm === 'edit' && (
                <form className="payment-form" onSubmit={handleEdit}>
                  <div className="payment-form-row">
                    <label className="payment-form-label">
                      Período
                      <input
                        className="payment-form-input"
                        type="text"
                        value={editPayment?.period ?? ''}
                        disabled
                      />
                    </label>
                    <label className="payment-form-label">
                      Arriendo cobrado / total ingresos
                      <input
                        className="payment-form-input"
                        type="text"
                        inputMode="numeric"
                        value={editAmount}
                        onChange={e => setEditAmount(formatAmountInput(e.target.value))}
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <label className="payment-form-label">
                      Fecha pago
                      <input
                        className="payment-form-input"
                        type="date"
                        value={editDate}
                        onChange={e => setEditDate(e.target.value)}
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <label className="payment-form-label">
                      Nota
                      <input
                        className="payment-form-input"
                        type="text"
                        value={editNote}
                        onChange={e => setEditNote(e.target.value)}
                        placeholder="opcional"
                        disabled={!!pendingOverpaymentDraft}
                      />
                    </label>
                    <div className="deductions-section">
                      <span className="deductions-section-label">Descuentos / liquidación al dueño</span>
                      {editDeductions.map((row, i) => (
                        <div key={i} className="deduction-row">
                          <input
                            className="payment-form-input deduction-input-label"
                            type="text"
                            value={row.label}
                            onChange={e => setEditDeductions(prev => prev.map((r, j) => j === i ? { ...r, label: e.target.value } : r))}
                            placeholder="Concepto"
                            disabled={!!pendingOverpaymentDraft}
                          />
                          <input
                            className="payment-form-input deduction-input-amount"
                            type="text"
                            inputMode="numeric"
                            value={row.amount}
                            onChange={e => setEditDeductions(prev => prev.map((r, j) => j === i ? { ...r, amount: formatAmountInput(e.target.value) } : r))}
                            placeholder="0"
                            disabled={!!pendingOverpaymentDraft}
                          />
                          <input
                            className="payment-form-input deduction-input-note"
                            type="text"
                            value={row.note}
                            onChange={e => setEditDeductions(prev => prev.map((r, j) => j === i ? { ...r, note: e.target.value } : r))}
                            placeholder="Nota opcional"
                            disabled={!!pendingOverpaymentDraft}
                          />
                          {!pendingOverpaymentDraft && (
                            <button
                              type="button"
                              className="btn-link-secondary"
                              onClick={() => setEditDeductions(prev => prev.filter((_, j) => j !== i))}
                            >
                              ×
                            </button>
                          )}
                        </div>
                      ))}
                      {!pendingOverpaymentDraft && (
                        <button
                          type="button"
                          className="btn-link-secondary"
                          onClick={() => setEditDeductions(prev => [...prev, { label: '', amount: '', note: '' }])}
                        >
                          + Agregar descuento
                        </button>
                      )}
                      {brokerEnabled && !pendingOverpaymentDraft && (
                        <div className="broker-helper">
                          <span className="broker-helper-label">Corredora</span>
                          <span className="broker-helper-diff">
                            Diferencia: <strong>{formatCLP(editBrokerDiff)}</strong>
                            {editBrokerDiff > usualBrokerFee && (
                              <span className="text-muted">
                                {' · '}Corredora: {formatCLP(usualBrokerFee)}
                                {' · '}Pendiente: <strong style={{ color: 'var(--warn, #b45309)' }}>{formatCLP(editBrokerDiff - usualBrokerFee)}</strong>
                              </span>
                            )}
                          </span>
                          {editBrokerDiff > 0 && usualBrokerFee > 0 && (
                            <button
                              type="button"
                              className="btn-link-secondary"
                              onClick={() => imputarCorredora(editBrokerDiff, editDeductions, setEditDeductions)}
                            >
                              Imputar diferencia a corredora
                            </button>
                          )}
                        </div>
                      )}
                      <span className="text-muted" style={{ fontSize: '0.85em' }}>
                        Esperado: {formatCLP(editExpected)}
                        {' · '}Pagado: {formatCLP(editPaidAmt)}
                        {editTotalDeductions > 0 && <>{' · '}Descuentos: {formatCLP(editTotalDeductions)}</>}
                        {' · '}Reconocido: <strong style={{ color: 'var(--ink)' }}>{formatCLP(editRecognized)}</strong>
                        {editMissing > 0 && (
                          <>{' · '}Pendiente: <strong style={{ color: 'var(--warn, #b45309)' }}>{formatCLP(editMissing)}</strong></>
                        )}
                        {' · '}Estado: <strong style={{ color: 'var(--ink)' }}>{statusPreview(editRecognized, editExpected)}</strong>
                        {ggccEnabled && editOwnerExpenseTotal > 0 && (
                          <>{' · '}Gasto dueño: {formatCLP(editOwnerExpenseTotal)}{' · '}Neto dueño: <strong style={{ color: 'var(--ink)' }}>{formatCLP(editNetOwner)}</strong></>
                        )}
                      </span>
                    </div>
                    {ggccEnabled && !pendingOverpaymentDraft && (
                      <div className="ggcc-section">
                        <span className="ggcc-section-label">GG.CC. — Gasto dueño</span>
                        <input
                          className="payment-form-input"
                          type="text"
                          inputMode="numeric"
                          value={editGgcc}
                          onChange={e => setEditGgcc(formatAmountInput(e.target.value))}
                          placeholder="Monto GG.CC."
                        />
                        {editGgcc === '' && (
                          <span className="text-muted" style={{ fontSize: '0.85em' }}>
                            Puedes registrar los GG.CC. después.
                          </span>
                        )}
                      </div>
                    )}
                    {!pendingOverpaymentDraft && (
                      <div className="payment-form-actions">
                        <button className="btn-primary" type="submit" disabled={isSubmitting}>
                          {isSubmitting ? 'Guardando…' : 'Guardar'}
                        </button>
                        <button className="btn-secondary" type="button" onClick={cancelForm}>
                          Cancelar
                        </button>
                      </div>
                    )}
                  </div>
                  {pendingOverpaymentDraft?.source === 'edit' && overpaymentPanel}
                  {formError && <div className="payment-form-error">{formError}</div>}
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default PaymentsView
