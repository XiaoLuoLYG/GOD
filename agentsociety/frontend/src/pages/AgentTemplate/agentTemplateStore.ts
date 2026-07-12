import { makeAutoObservable } from 'mobx';
import { ApiAgentParam, ApiAgentTemplate, BlockContextInfo } from '../../types/agentTemplate';
import React from 'react';
import { fetchCustom } from '../../components/fetch';
import { profiles } from './profile';

class AgentTemplateStore {
  agentParam: ApiAgentParam | null = null;
  suggestions: any[] = [];
  agentType?: string;
  agentClass?: string;
  agentClasses: { value: string; label: string }[] = [];
  loadingAgentClasses: boolean = false;
  currentTemplate: ApiAgentTemplate | null = null;
  blockContexts: BlockContextInfo[] = [];

  constructor() {
    makeAutoObservable(this);
  }

  setAgentInfo(info: ApiAgentParam | null) {
    this.agentParam = info;
  }

  setSuggestions(suggestions: any[]) {
    this.suggestions = suggestions;
  }

  async setAgentType(type: string | undefined) {
    this.agentType = type;
    if (type) {
      await this.fetchAgentClasses(type);
    }
    await this.setAgentClass(undefined);
  }

  async setAgentClass(agentClass: string | undefined) {
    this.agentClass = agentClass;
    await this.fetchAgentInfo();
  }

  setAgentClasses(classes: { value: string; label: string }[]) {
    this.agentClasses = classes;
  }

  setLoadingAgentClasses(loading: boolean) {
    this.loadingAgentClasses = loading;
  }

  setCurrentTemplate(template: ApiAgentTemplate | null) {
    this.currentTemplate = template;
  }

  setBlockContexts(contexts: BlockContextInfo[]) {
    this.blockContexts = contexts;
  }

  async fetchAgentClasses(agentType: string) {
    this.setLoadingAgentClasses(true);
    try {
      const response = await fetchCustom(`/api/agent-classes?agent_type=${agentType}`);
      if (response.ok) {
        const data = await response.json();
        if (data.data) {
          this.setAgentClasses(data.data);
        }
      }
    } catch (error) {
      console.error('Failed to fetch agent classes:', error);
      this.setAgentClasses([]);
    } finally {
      this.setLoadingAgentClasses(false);
    }
  }

  async fetchAgentInfo() {
    if (!this.agentType || !this.agentClass) {
      this.setAgentInfo(null);
      this.setSuggestions([]);
      return;
    }

    try {
      const response = await fetch(`/api/agent-param?agent_type=${this.agentType}&agent_class=${this.agentClass}`);
      const data = await response.json();

      if (data.data) {
        const newAgentInfo = data.data as ApiAgentParam;
        this.setAgentInfo(newAgentInfo);

        // Generate suggestions
        const profileSuggestions = profiles.map((profile) => ({
          label: profile.name,
          detail: profile.description
        }));

        const contextSuggestions = newAgentInfo.context.map((value) => ({
          label: value.name,
          detail: value.description || `Type: ${value.type}`
        }));

        const statusSuggestions = newAgentInfo.status_attributes.map((attr) => ({
          label: attr.name,
          detail: attr.description || `Type: ${attr.type}`
        }));
        if (this.agentType === 'citizen') {
          this.setSuggestions([
            { label: 'profile', children: profileSuggestions },
            { label: 'context', children: contextSuggestions },
            { label: 'status', children: statusSuggestions }
          ]);
        } else if (this.agentType === 'supervisor') {
          this.setSuggestions([
            { label: 'context', children: contextSuggestions },
            { label: 'status', children: statusSuggestions }
          ]);
        }
      } else {
        this.setAgentInfo(null);
        this.setSuggestions([]);
      }
    } catch (err) {
      console.error('Failed to fetch agent parameters:', err);
      this.setAgentInfo(null);
      this.setSuggestions([]);
    }
  }

  async fetchTemplateById(id: string) {
    try {
      const response = await fetchCustom(`/api/agent-templates/${id}`);
      if (response.ok) {
        const template = (await response.json()).data as ApiAgentTemplate;
        this.setCurrentTemplate(template);

        if (template.agent_type) {
          await this.setAgentType(template.agent_type);
        }
        if (template.agent_class) {
          await this.setAgentClass(template.agent_class);
        }

        return template;
      }
    } catch (error) {
      console.error('Failed to fetch template:', error);
      return null;
    }
  }

  async createTemplate(templateData: any) {
    try {
      const res = await fetchCustom('/api/agent-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(templateData),
      });

      if (!res.ok) {
        const errorData = await res.json();
        if (errorData.detail) {
          throw new Error(typeof errorData.detail === 'object' ? JSON.stringify(errorData.detail) : errorData.detail);
        } else {
          throw new Error('Failed to create template: ' + JSON.stringify(errorData));
        }
      }

      return true;
    } catch (error) {
      throw error;
    }
  }
}

export const agentTemplateStore = new AgentTemplateStore();
export const AgentTemplateStoreContext = React.createContext(agentTemplateStore);
