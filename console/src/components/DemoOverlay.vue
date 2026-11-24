<script setup lang="ts">
import { DEMO_STEPS, demoCaption, demoCursor, demoRing, demoRunning, demoStepIndex, stopDemo } from '../demo'
import { t } from '../i18n'
</script>

<template>
  <div v-if="demoRunning" class="demo-layer" aria-hidden="false">
    <div
      v-if="demoRing"
      class="demo-ring"
      :style="{ transform: `translate(${demoRing.x}px, ${demoRing.y}px)`, width: `${demoRing.w}px`, height: `${demoRing.h}px` }"
    ></div>
    <div
      v-show="demoCursor.visible"
      class="demo-cursor"
      :class="{ clicking: demoCursor.clicking }"
      :style="{ transform: `translate(${demoCursor.x}px, ${demoCursor.y}px)` }"
    >
      <span class="demo-ripple"></span>
      <svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
        <path d="M3 2l7.5 19 2.6-7.4L20.5 11z" />
      </svg>
    </div>
    <div class="demo-bar" role="status" aria-live="polite">
      <span class="demo-tag">{{ t('demoMode') }} · {{ demoStepIndex + 1 }}/{{ DEMO_STEPS.length }}</span>
      <span class="demo-caption">{{ demoCaption ? t(demoCaption) : '' }}</span>
      <button type="button" class="btn demo-stop" @click="stopDemo">{{ t('demoStop') }} <span class="kbd">Esc</span></button>
    </div>
  </div>
</template>

<style scoped>
.demo-layer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  pointer-events: none;
}

.demo-ring {
  position: fixed;
  top: 0;
  left: 0;
  border: 2px solid var(--c-amber);
  border-radius: var(--radius-1);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--c-amber) 25%, transparent);
  transition:
    transform 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    width 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    height 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.demo-cursor {
  position: fixed;
  top: 0;
  left: 0;
  transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

/* The arrow's tip sits on the point the cursor moves to. */
.demo-cursor svg {
  position: absolute;
  top: -2px;
  left: -3px;
  fill: #ffffff;
  stroke: #101727;
  stroke-width: 1.6;
  stroke-linejoin: round;
  filter: drop-shadow(0 2px 3px rgb(0 0 0 / 0.35));
  transition: transform 0.15s ease;
}

.demo-cursor.clicking svg {
  transform: scale(0.85);
}

.demo-ripple {
  position: absolute;
  top: -18px;
  left: -18px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--c-amber) 45%, transparent);
  opacity: 0;
  transform: scale(0.3);
}

.demo-cursor.clicking .demo-ripple {
  animation: demo-ripple 0.5s ease-out;
}

@keyframes demo-ripple {
  from {
    opacity: 1;
    transform: scale(0.3);
  }
  to {
    opacity: 0;
    transform: scale(1.4);
  }
}

.demo-bar {
  position: fixed;
  inset-inline: 16px;
  bottom: 16px;
  display: flex;
  gap: var(--space-3);
  align-items: center;
  max-inline-size: 760px;
  margin-inline: auto;
  padding: 10px 12px 10px 16px;
  color: var(--c-on-primary);
  background: var(--c-primary);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgb(0 0 0 / 0.25);
  pointer-events: auto;
}

.demo-tag {
  flex: none;
  font-size: var(--fs-12);
  font-weight: 600;
  opacity: 0.75;
}

.demo-caption {
  flex: 1 1 auto;
  font-size: var(--fs-16);
  font-weight: 500;
}

.demo-stop {
  flex: none;
}

@media (max-width: 700px) {
  .demo-bar {
    flex-wrap: wrap;
  }

  .demo-caption {
    flex-basis: 100%;
    order: 3;
    font-size: var(--fs-14);
  }

  .demo-stop {
    margin-inline-start: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .demo-cursor,
  .demo-ring {
    transition: none;
  }

  .demo-cursor.clicking .demo-ripple {
    animation: none;
  }
}
</style>
