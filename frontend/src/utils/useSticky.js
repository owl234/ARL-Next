import { ref, computed, onMounted, onUnmounted, isRef } from 'vue';

export function useSticky(actionBarRef, offsetModifier = 24) {
  const stickyTopNumber = ref(180);
  const actionBarHeight = ref(180);
  const scrollContainer = ref(null);
  let resizeObserver = null;

  const stickyConfig = computed(() => {
    if (!scrollContainer.value) return false;
    return {
      offsetHeader: stickyTopNumber.value,
      getContainer: () => scrollContainer.value
    };
  });

  onMounted(() => {
    scrollContainer.value = document.querySelector('.ant-layout-content');
    const getTargetEl = () => (isRef(actionBarRef) ? actionBarRef.value : actionBarRef);

    const updateSticky = () => {
      const el = getTargetEl();
      if (el && typeof el.getBoundingClientRect === 'function') {
        const rect = el.getBoundingClientRect();
        stickyTopNumber.value = rect.height;
        actionBarHeight.value = rect.height;
      }
    };
    resizeObserver = new ResizeObserver(updateSticky);
    const targetEl = getTargetEl();
    if (targetEl) resizeObserver.observe(targetEl);
    updateSticky();
  });

  onUnmounted(() => {
    if (resizeObserver) resizeObserver.disconnect();
  });

  return {
    stickyConfig,
    actionBarHeight,
    stickyTopNumber,
    scrollContainer
  };
}
